import asyncio
import json
import re
import time
from pathlib import Path

import nodriver as uc
from nodriver import cdp

from .versions import to_apkmirror_version

APP_SITES = {
    "youtube": {"org": "google-inc", "slug": "youtube"},
    "youtube-music": {"org": "google-inc", "slug": "youtube-music"},
    "reddit": {"org": "reddit-inc", "slug": "reddit"},
    "twitter": {"org": "x-corp", "slug": "twitter", "release_slug": "x"},
    "instagram": {"org": "instagram", "slug": "instagram"},
    "github": {"org": "github", "slug": "github-2", "release_slug": "github"},
    "niagara-launcher": {
        "org": "mellowdrop-studio",
        "slug": "niagara-launcher-🔹-fresh-clean",
        "release_slug": "niagara-launcher-‧-home-screen",
    },
    "pydroid3": {"org": "lider-soft-kz", "slug": "pydroid-3-ide-for-python-3"},
    "smart-launcher": {
        "org": "smart-launcher-team",
        "slug": "smart-launcher",
        "release_slug": "smart-launcher-6-‧-home-screen",
    },
    "wps-office": {"org": "wps-software-pte-ltd", "slug": "wps-office-pdf"},
    "gboard": {"org": "google-inc", "slug": "gboard", "release_slug": "gboard-the-google-keyboard"},
    "speedtest": {"org": "ookla", "slug": "speedtest"},
    "solid-explorer": {"org": "neatbytes", "slug": "solid-explorer-file-manager"},
    "brave": {"org": "brave-software", "slug": "brave-browser", "release_slug": "brave-private-web-browser-vpn"},
    "nova-launcher": {"org": "instabridge-sweden-ab", "slug": "nova-launcher"},
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36"

# NOT: nodriver'ın element-handle tabanli select()/select_all() API'si CDP
# node referanslarini sayfa gecisleri arasinda kaybediyor. Bu yuzden burada
# SADECE tab.get() (navigasyon) ve tab.evaluate() (JS ile veri cekme/tiklama)
# kullaniliyor. Dosya indirme de artik ayri bir httpx istegi yerine CDP'nin
# kendi indirme mekanizmasi (Browser.setDownloadBehavior) ile, tarayicinin
# GERCEK oturumu (cookie/Cloudflare dogrulamasi dahil) uzerinden yapiliyor -
# APKMirror'in indirme linkini disaridan istekle 403'lemesi sorununu cozer.


async def _start_browser(retries: int = 4, base_delay: float = 3.0):
    last_err = None
    for attempt in range(retries):
        try:
            return await uc.start(
                headless=True,
                no_sandbox=True,
                browser_args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    f"--user-agent={USER_AGENT}",
                ],
            )
        except Exception as e:
            last_err = e
            delay = base_delay * (attempt + 1)
            print(f"⚠️ Tarayıcı başlatılamadı (deneme {attempt + 1}/{retries}): {e} - {delay:.0f}s sonra tekrar denenecek")
            await asyncio.sleep(delay)
    raise last_err


async def _enable_downloads(tab, out_dir: Path):
    try:
        await tab.send(cdp.browser.set_download_behavior(behavior="allow", download_path=str(out_dir)))
    except Exception as e:
        print(f"⚠️ set_download_behavior başarısız (yine de denenecek): {e}")


async def _wait_for_download(out_dir: Path, existing: set, timeout: float = 60.0):
    deadline = time.monotonic() + timeout
    last_sizes = {}

    while time.monotonic() < deadline:
        await asyncio.sleep(1.0)
        try:
            current = {f.name: f for f in out_dir.iterdir() if f.is_file()}
        except FileNotFoundError:
            continue

        new_files = [
            f for name, f in current.items()
            if name not in existing and not name.endswith((".crdownload", ".tmp"))
        ]
        if not new_files:
            continue

        candidate = max(new_files, key=lambda f: f.stat().st_mtime)
        size = candidate.stat().st_size

        if size > 0 and last_sizes.get(candidate.name) == size:
            return candidate

        last_sizes[candidate.name] = size

    return None


async def _row_count(tab) -> int:
    try:
        result = await tab.evaluate("document.querySelectorAll('.table-row').length")
        return int(result or 0)
    except Exception:
        return 0


async def _page_exists(tab, url: str) -> bool:
    try:
        await tab.get(url)
        await tab.sleep(1.0)
        return (await _row_count(tab)) > 0
    except Exception:
        return False


async def _resolve_list_url(tab, app_config: dict, version: str) -> str:
    version_slug = to_apkmirror_version(version)
    name_part = app_config.get("release_slug") or app_config["slug"]
    folder_url = f"https://www.apkmirror.com/apk/{app_config['org']}/{app_config['slug']}"

    candidates = [
        f"{folder_url}/{name_part}-{version_slug}-release/",
        f"{folder_url}/{name_part}-{version_slug}-release-0-release/",
        f"{folder_url}/{name_part}-{version_slug}-beta-0-release/",
        f"{folder_url}/{name_part}-{version_slug}-beta-1-release/",
    ]

    for candidate in candidates:
        print("🔎 TRY:", candidate)
        if await _page_exists(tab, candidate):
            return candidate

    print("⚠️ No direct match, scanning app listing page...")
    listing_url = f"{folder_url}/"

    slug_part = f"-{version_slug}-"
    js = f"""
    (() => {{
        const links = Array.from(document.querySelectorAll("a[href*='-release/']"));
        const match = links.find(a => a.getAttribute('href').includes({json.dumps(slug_part)}));
        return match ? match.href : null;
    }})()
    """

    for attempt in range(2):
        await tab.get(listing_url)
        await tab.sleep(1.5 + attempt)
        found_url = await tab.evaluate(js)
        if found_url:
            return found_url

    raise RuntimeError(f"No APKMirror release page found for version {version}")


async def _extract_variant_url(tab, force_build: str | None, app_name: str) -> str | None:
    js = f"""
    (() => {{
        const rows = document.querySelectorAll('.table-row');
        let standaloneNodpi = null, standaloneAnyDpi = null, bundleNodpi = null, bundleAnyDpi = null;
        const allowedArchs = ['universal', 'evrensel', 'noarch', 'arm64-v8a', 'arm64-v8a + armeabi-v7a', 'arm64-v8a + armeabi'];
        const forceBuild = {json.dumps(force_build)};
        const appName = {json.dumps(app_name)};

        for (const row of rows) {{
            const cells = row.querySelectorAll('.table-cell');
            if (cells.length < 4) continue;

            const link = cells[0].querySelector('a.accent_color');
            if (!link) continue;

            if (forceBuild && !cells[0].innerText.includes(forceBuild)) continue;

            const badge = cells[0].querySelector('.apkm-badge');
            const badgeText = badge ? badge.innerText.toUpperCase() : '';
            const isBundle = badgeText.includes('BUNDLE') || badgeText.includes('PAKET');

            if (appName === 'instagram' && !isBundle) continue;

            const archText = (cells[1].innerText || '').trim().toLowerCase();
            const dpiText = (cells[3].innerText || '').trim().toLowerCase();

            const isTargetArch = archText === '' || allowedArchs.some(a => archText.includes(a));
            const isTargetDpi = dpiText === '' || dpiText.includes('nodpi') || dpiText.includes('anydpi') || /\\d+-640dpi/.test(dpiText);

            if (isTargetArch && isTargetDpi) {{
                if (!isBundle) {{
                    if (dpiText.includes('nodpi')) standaloneNodpi = link.href; else standaloneAnyDpi = link.href;
                }} else {{
                    if (dpiText.includes('nodpi')) bundleNodpi = link.href; else bundleAnyDpi = link.href;
                }}
            }}
        }}

        return standaloneNodpi || standaloneAnyDpi || bundleNodpi || bundleAnyDpi;
    }})()
    """
    return await tab.evaluate(js)


async def download_apk(version: str, app_name: str = "youtube", force_build: str | None = None) -> str:
    app_config = APP_SITES.get(app_name)
    if not app_config:
        raise RuntimeError(f'Unknown appName "{app_name}" - not found in APP_SITES')

    out_dir = Path(__file__).resolve().parent.parent / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)

    browser = await _start_browser()

    try:
        tab = browser.main_tab
        await _enable_downloads(tab, out_dir)

        list_url = await _resolve_list_url(tab, app_config, version)
        print("🌐 LIST:", list_url)

        await tab.get(list_url)
        await tab.sleep(1.2)

        variant_url = await _extract_variant_url(tab, force_build, app_name)
        if not variant_url:
            raise RuntimeError("No matching variant found on APKMirror")
        if variant_url.startswith("/"):
            variant_url = "https://www.apkmirror.com" + variant_url

        print("➡️ VARIANT:", variant_url)

        await tab.get(variant_url)
        await tab.sleep(1.2)

        existing_before = {f.name for f in out_dir.iterdir() if f.is_file()}

        print("⬇️ Clicking main download button...")
        await tab.evaluate("document.querySelector('a.downloadButton')?.click()")

        downloaded = await _wait_for_download(out_dir, existing_before, timeout=20)

        if not downloaded:
            print("⚠️ Doğrudan indirme başlamadı, confirm sayfası bekleniyor...")
            await tab.sleep(1.5)

            final_href = await tab.evaluate(
                "(() => { const el = document.querySelector('#download-link'); return el ? el.getAttribute('href') : null; })()"
            )

            if final_href:
                print("🔗 Clicking final download link...")
                await tab.evaluate("document.querySelector('#download-link')?.click()")
                downloaded = await _wait_for_download(out_dir, existing_before, timeout=60)

        if not downloaded:
            raise RuntimeError("İndirme başlamadı / dosya tespit edilemedi (CDP download).")

        size = downloaded.stat().st_size
        if size < 1024:
            raise RuntimeError(f"İndirilen dosya çok küçük ({size} bayt)")

        print("📦 DONE:", downloaded, f"({size / 1024 / 1024:.2f} MB)")
        return str(downloaded)

    finally:
        browser.stop()


async def get_latest_listing(app_name: str) -> dict | None:
    app_config = APP_SITES.get(app_name)
    if not app_config:
        raise RuntimeError(f'Unknown appName "{app_name}" - not found in APP_SITES')

    browser = await _start_browser()

    try:
        tab = browser.main_tab
        listing_url = f"https://www.apkmirror.com/apk/{app_config['org']}/{app_config['slug']}/"
        print("🌐 LISTING:", listing_url)

        js = """
        (() => {
            const link = document.querySelector("a[href*='-release/']");
            if (!link) return null;
            const row = link.closest('div, li, tr') || link.parentElement;
            const text = row ? row.innerText : link.innerText;
            return { href: link.href, text: text || '' };
        })()
        """

        result = None
        for attempt in range(3):
            await tab.get(listing_url)
            await tab.sleep(1.5 + attempt)
            result = await tab.evaluate(js)
            if result:
                break
            print(f"⚠️ Liste sayfasında link bulunamadı, tekrar deneniyor ({attempt + 1}/3)...")

        if not result:
            return None

        text = result.get("text", "") if isinstance(result, dict) else ""
        href = result.get("href") if isinstance(result, dict) else None

        match = re.search(r"\d+(?:\.\d+)+", text)

        return {"version": match.group(0) if match else None, "href": href}

    finally:
        browser.stop()
