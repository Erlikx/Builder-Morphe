import asyncio
import json
import re
import subprocess
import time
from pathlib import Path

import httpx
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
# node referanslarini sayfa gecisleri arasinda kaybediyor ("Could not find
# node with given id"). Bu yuzden burada SADECE tab.get() (navigasyon) ve
# tab.evaluate() (JS ile veri cekme) kullaniliyor - orijinal Playwright
# kodunun page.evaluate() yaklasimiyla ayni mantik, nodriver'da daha guvenilir.


def _kill_stray_chrome() -> None:
    """Clean up orphaned Chrome processes left behind by a failed uc.start().

    If uc.start() fails to establish the CDP websocket, the Chrome process it
    already spawned is never handed back to us, so it never gets stopped.
    Left running, it can block/confuse the next browser launch, which is
    what causes consecutive "Failed to connect to browser" errors to chain
    together (e.g. YouTube -> YouTube Music -> Reddit all failing in a row).
    """
    for pattern in ("--remote-debugging-port", "headless_shell", "chrome_crashpad"):
        try:
            subprocess.run(["pkill", "-9", "-f", pattern], check=False,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass


async def _start_browser(retries: int = 3):
    last_err: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            return await uc.start(
                headless=True,
                sandbox=False,  # real nodriver Config field (no_sandbox=True was a no-op)
                browser_args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    f"--user-agent={USER_AGENT}",
                ],
            )
        except Exception as e:
            last_err = e
            print(f"⚠️ Browser start failed (attempt {attempt}/{retries}): {e}")
            _kill_stray_chrome()
            await asyncio.sleep(2 * attempt)

    raise RuntimeError(f"Failed to start browser after {retries} attempts: {last_err}")


async def _safe_stop(browser) -> None:
    try:
        browser.stop()
    except Exception:
        pass


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
    await tab.get(listing_url)
    await tab.sleep(1.0)

    slug_part = f"-{version_slug}-"
    js = f"""
    (() => {{
        const links = Array.from(document.querySelectorAll("a[href*='-release/']"));
        const match = links.find(a => a.getAttribute('href').includes({json.dumps(slug_part)}));
        return match ? match.href : null;
    }})()
    """
    found_url = await tab.evaluate(js)

    if not found_url:
        raise RuntimeError(f"No APKMirror release page found for version {version}")

    return found_url


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


async def _download_via_browser(tab, final_url: str, out_dir: Path, timeout_s: int = 180) -> Path:
    """Download the APK using Chrome's own network stack.

    APKMirror sits behind a WAF that TLS/HTTP-fingerprints requests. Pages
    load fine through the real browser (which is why we get all the way to
    a final URL), but a bare httpx GET to that same URL gets 403'd because
    it doesn't look like a browser request - even carrying the right
    cookies. Routing the actual download through Chrome (via CDP's download
    interception) reuses the exact same TLS/HTTP fingerprint and cookie jar
    that already passed the WAF, so it goes through cleanly.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    before = {p.name for p in out_dir.iterdir()}

    await tab.send(cdp.browser.set_download_behavior(behavior="allow", download_path=str(out_dir)))
    await tab.get(final_url)

    deadline = time.time() + timeout_s
    stable_candidate: Path | None = None
    last_size = -1

    while time.time() < deadline:
        await asyncio.sleep(1.0)
        current = {p.name for p in out_dir.iterdir()}
        new_names = [n for n in (current - before) if not n.endswith(".crdownload")]

        if new_names:
            candidate = out_dir / new_names[0]
            try:
                size = candidate.stat().st_size
            except FileNotFoundError:
                continue

            if size > 0 and size == last_size:
                stable_candidate = candidate
                break
            last_size = size
        else:
            last_size = -1

    if not stable_candidate:
        raise RuntimeError("Browser download did not complete in time")

    return stable_candidate


async def download_apk(version: str, app_name: str = "youtube", force_build: str | None = None) -> str:
    app_config = APP_SITES.get(app_name)
    if not app_config:
        raise RuntimeError(f'Unknown appName "{app_name}" - not found in APP_SITES')

    browser = await _start_browser()

    try:
        tab = browser.main_tab

        list_url = await _resolve_list_url(tab, app_config, version)
        print("🌐 LIST:", list_url)

        await tab.get(list_url)
        await tab.sleep(1.0)

        variant_url = await _extract_variant_url(tab, force_build, app_name)
        if not variant_url:
            raise RuntimeError("No matching variant found on APKMirror")

        print("➡️ VARIANT:", variant_url)

        await tab.get(variant_url)
        await tab.sleep(1.0)

        confirm_href = await tab.evaluate(
            "(() => { const el = document.querySelector('a.downloadButton'); return el ? el.getAttribute('href') : null; })()"
        )
        if not confirm_href:
            raise RuntimeError("Download button not found")
        if confirm_href.startswith("/"):
            confirm_href = "https://www.apkmirror.com" + confirm_href

        print("⬇️ Confirm page:", confirm_href)
        await tab.get(confirm_href)
        await tab.sleep(1.0)

        final_url = await tab.evaluate(
            "(() => { const el = document.querySelector('#download-link'); return el ? el.getAttribute('href') : null; })()"
        )
        if not final_url:
            raise RuntimeError("Final download link not found")
        if final_url.startswith("/"):
            final_url = "https://www.apkmirror.com" + final_url

        print("🔗 Final URL:", final_url)

        out_dir = Path(__file__).resolve().parent.parent / "downloads"
        out_dir.mkdir(parents=True, exist_ok=True)

        downloaded_path = await _download_via_browser(tab, final_url, out_dir)

        file_name = final_url.split("/")[-1].split("?")[0] or f"{app_name}.apk"
        if not file_name.endswith(".apk"):
            file_name = f"{app_name}-{version}.apk"

        file_path = out_dir / file_name
        if downloaded_path != file_path:
            if file_path.exists():
                file_path.unlink()
            downloaded_path.replace(file_path)

        size = file_path.stat().st_size
        if size < 1024:
            raise RuntimeError(f"Downloaded file too small ({size} bytes) - muhtemelen 403/hata sayfasi indi")

        print("📦 DONE:", file_path, f"({size / 1024 / 1024:.2f} MB)")
        return str(file_path)

    finally:
        await _safe_stop(browser)


async def get_latest_listing(app_name: str) -> dict | None:
    app_config = APP_SITES.get(app_name)
    if not app_config:
        raise RuntimeError(f'Unknown appName "{app_name}" - not found in APP_SITES')

    browser = await _start_browser()

    try:
        tab = browser.main_tab
        listing_url = f"https://www.apkmirror.com/apk/{app_config['org']}/{app_config['slug']}/"
        print("🌐 LISTING:", listing_url)

        await tab.get(listing_url)
        await tab.sleep(1.0)

        js = """
        (() => {
            const link = document.querySelector("a[href*='-release/']");
            if (!link) return null;
            const row = link.closest('div, li, tr') || link.parentElement;
            const text = row ? row.innerText : link.innerText;
            return { href: link.href, text: text || '' };
        })()
        """
        result = await tab.evaluate(js)

        if not result:
            return None

        text = result.get("text", "") if isinstance(result, dict) else ""
        href = result.get("href") if isinstance(result, dict) else None

        match = re.search(r"\d+(?:\.\d+)+", text)

        return {"version": match.group(0) if match else None, "href": href}

    finally:
        await _safe_stop(browser)
