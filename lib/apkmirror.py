import asyncio
import json
import random
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
    "gboard": {"org": "google-inc", "slug": "gboard", "release_slug": "gboard-the-google-keyboard"},
    "speedtest": {"org": "ookla", "slug": "speedtest"},
    "solid-explorer": {"org": "neatbytes", "slug": "solid-explorer-file-manager"},
    "brave": {"org": "brave-software", "slug": "brave-browser", "release_slug": "brave-private-web-browser-vpn"},
    "proton-vpn": {
        "org": "proton-technologies-ag",
        "slug": "protonvpn-secure-and-free-vpn",
        "release_slug": "proton-vpn-fast-secure-vpn",
    },
    "tiktok": {"org": "tiktok-pte-ltd", "slug": "tik-tok-including-musical-ly", "release_slug": "tiktok"},
    "warp": {
        "org": "cloudflare",
        "slug": "1-1-1-1-faster-safer-internet",
        "release_slug": "1-1-1-1-warp-safer-internet",
    },
    "inshot": {
        "org": "inshot-inc",
        "slug": "inshot-video-editor-photo-editor",
        "release_slug": "video-editor-maker-inshot",
    },
    "google-photos": {"org": "google-inc", "slug": "photos", "release_slug": "google-photos"},
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36"

DIAGNOSTICS_DIR = Path(__file__).resolve().parent.parent / "diagnostics"

_CHALLENGE_MARKERS = [
    "just a moment",
    "checking your browser",
    "attention required! | cloudflare",
    "verify you are human",
    "cf-browser-verification",
    "cf_chl_",
    "ddos protection by cloudflare",
]

# NOT: nodriver'ın element-handle tabanli select()/select_all() API'si CDP
# node referanslarini sayfa gecisleri arasinda kaybediyor. Bu yuzden burada
# SADECE tab.get() (navigasyon) ve tab.evaluate() (JS ile veri cekme/tiklama)
# kullaniliyor. Dosya indirme de ayri bir httpx istegi yerine CDP'nin kendi
# indirme mekanizmasi (Browser.setDownloadBehavior) ile, tarayicinin GERCEK
# oturumu (cookie/Cloudflare dogrulamasi dahil) uzerinden yapiliyor.

_shared_browser = None
_downloads_ready = False
_challenge_hits = 0
_cooldown_until = 0.0


async def _jitter_sleep(base: float, spread: float = 0.6) -> None:
    """Sabit sleep() yerine rastgele (insan benzeri) bekleme."""
    await asyncio.sleep(base + random.uniform(0, spread))


async def get_browser():
    """
    Tüm run boyunca TEK bir tarayıcı örneği paylaşılır - her uygulama için
    yeniden başlatmak hem yavaş hem de "art arda yeni tarayıcı açılışı"
    paterni oluşturarak bot tespiti riskini artırıyordu.
    """
    global _shared_browser

    if _shared_browser is not None:
        return _shared_browser

    retries = 4
    base_delay = 3.0
    last_err = None

    for attempt in range(retries):
        try:
            _shared_browser = await uc.start(
                headless=True,
                no_sandbox=True,
                browser_args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                    f"--user-agent={USER_AGENT}",
                ],
            )
            return _shared_browser
        except Exception as e:
            last_err = e
            delay = base_delay * (attempt + 1)
            print(f"⚠️ Tarayıcı başlatılamadı (deneme {attempt + 1}/{retries}): {e} - {delay:.0f}s sonra tekrar denenecek")
            await asyncio.sleep(delay)

    raise last_err


async def close_browser():
    """Run'ın en sonunda main.py tarafından çağrılır."""
    global _shared_browser, _downloads_ready
    if _shared_browser is not None:
        try:
            _shared_browser.stop()
        except Exception:
            pass
        _shared_browser = None
        _downloads_ready = False


async def _enable_downloads(tab, out_dir: Path):
    global _downloads_ready
    if _downloads_ready:
        return
    try:
        await tab.send(cdp.browser.set_download_behavior(behavior="allow", download_path=str(out_dir)))
        _downloads_ready = True
    except Exception as e:
        print(f"⚠️ set_download_behavior başarısız (yine de denenecek): {e}")


async def _is_challenge_page(tab) -> bool:
    try:
        content = await tab.evaluate("(document.title + ' ' + document.body.innerText.slice(0, 500)).toLowerCase()")
    except Exception:
        return False
    if not content:
        return False
    return any(marker in content for marker in _CHALLENGE_MARKERS)


async def _save_diagnostic_screenshot(tab, label: str):
    try:
        DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        path = DIAGNOSTICS_DIR / f"{label}-{ts}.png"
        await tab.save_screenshot(str(path))
        print(f"📸 Teşhis ekran görüntüsü kaydedildi: {path}")
    except Exception as e:
        print(f"⚠️ Ekran görüntüsü alınamadı: {e}")


async def _apply_global_cooldown():
    """
    Bir challenge görüldüğünde bu sadece o istek için değil, run'ın geri
    kalanı için de geçerli bir "yavaşla" sinyali - APKMirror/Cloudflare
    kümülatif istek hızına göre giderek sertleşen bir koruma uyguluyor
    gibi görünüyor (tek bir URL'e özel değil).
    """
    now = time.monotonic()
    if now < _cooldown_until:
        remaining = _cooldown_until - now
        print(f"🧊 Genel soğuma süresi aktif, {remaining:.0f}s bekleniyor...")
        await asyncio.sleep(remaining)


async def _goto(tab, url: str, wait: float = 1.2, challenge_retries: int = 3, label: str = "sayfa"):
    """
    Navigasyon + Cloudflare challenge tespiti. Sayfa "Just a moment..." gibi
    bir doğrulama ekranıyla karşılaşırsa, normal bir hata gibi davranmak
    yerine biraz bekleyip tekrar dener. Ayrıca her challenge görüldüğünde
    global bir soğuma süresi başlatılır (run boyunca birikimli - bkz.
    _apply_global_cooldown).
    """
    global _challenge_hits, _cooldown_until

    await _apply_global_cooldown()

    for attempt in range(challenge_retries + 1):
        await tab.get(url)
        await _jitter_sleep(wait)

        if await _is_challenge_page(tab):
            _challenge_hits += 1
            # Her yeni challenge'da hem bu deneme için hem de sonraki TÜM
            # isteklerde soğuma süresi katlanarak artıyor (15s, 30s, 60s...).
            cooldown_len = min(15.0 * (2 ** (_challenge_hits - 1)), 120.0)
            _cooldown_until = time.monotonic() + cooldown_len

            if attempt < challenge_retries:
                print(
                    f"🛡️ Cloudflare doğrulama ekranı tespit edildi ({label}), "
                    f"{cooldown_len:.0f}s soğuyup tekrar denenecek (toplam {_challenge_hits}. karşılaşma)..."
                )
                await asyncio.sleep(cooldown_len)
                continue

            print(f"⚠️ Cloudflare doğrulama ekranı hâlâ geçmedi ({label}), yine de devam ediliyor...")
            await _save_diagnostic_screenshot(tab, f"cloudflare-{label}")

        return


async def _row_count(tab) -> int:
    try:
        result = await tab.evaluate("document.querySelectorAll('.table-row').length")
        return int(result or 0)
    except Exception:
        return 0


async def _page_exists(tab, url: str) -> bool:
    try:
        await _goto(tab, url, wait=1.0, label="direct-try")
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
        await _goto(tab, listing_url, wait=1.5 + attempt, label="listing-scan")
        found_url = await tab.evaluate(js)
        if found_url:
            return found_url

    await _save_diagnostic_screenshot(tab, f"no-match-{app_config['slug']}")
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


async def download_apk(version: str, app_name: str = "youtube", force_build: str | None = None) -> str:
    app_config = APP_SITES.get(app_name)
    if not app_config:
        raise RuntimeError(f'Unknown appName "{app_name}" - not found in APP_SITES')

    out_dir = Path(__file__).resolve().parent.parent / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)

    browser = await get_browser()
    tab = browser.main_tab

    try:
        await _enable_downloads(tab, out_dir)

        list_url = await _resolve_list_url(tab, app_config, version)
        print("🌐 LIST:", list_url)

        variant_url = None
        for attempt in range(3):
            await _goto(tab, list_url, wait=1.2 + attempt * 0.8, label="list-page")
            variant_url = await _extract_variant_url(tab, force_build, app_name)
            if variant_url:
                break
            print(f"⚠️ Sayfada eşleşen satır bulunamadı, tekrar deneniyor ({attempt + 1}/3)...")

        if not variant_url:
            await _save_diagnostic_screenshot(tab, f"no-variant-{app_name}")
            raise RuntimeError("No matching variant found on APKMirror")
        if variant_url.startswith("/"):
            variant_url = "https://www.apkmirror.com" + variant_url

        print("➡️ VARIANT:", variant_url)

        await _goto(tab, variant_url, wait=1.2, label="variant-page")

        existing_before = {f.name for f in out_dir.iterdir() if f.is_file()}

        print("⬇️ Clicking main download button...")
        await tab.evaluate("document.querySelector('a.downloadButton')?.click()")

        downloaded = await _wait_for_download(out_dir, existing_before, timeout=20)

        if not downloaded:
            print("⚠️ Doğrudan indirme başlamadı, confirm sayfası bekleniyor...")
            await _jitter_sleep(1.5)

            final_href = await tab.evaluate(
                "(() => { const el = document.querySelector('#download-link'); return el ? el.getAttribute('href') : null; })()"
            )

            if final_href:
                print("🔗 Clicking final download link...")
                await tab.evaluate("document.querySelector('#download-link')?.click()")
                downloaded = await _wait_for_download(out_dir, existing_before, timeout=60)

        if not downloaded:
            await _save_diagnostic_screenshot(tab, f"no-download-{app_name}")
            raise RuntimeError("İndirme başlamadı / dosya tespit edilemedi (CDP download).")

        size = downloaded.stat().st_size
        if size < 1024:
            raise RuntimeError(f"Downloaded file too small ({size} bytes)")

        print("📦 DONE:", downloaded, f"({size / 1024 / 1024:.2f} MB)")
        return str(downloaded)

    except Exception:
        await _save_diagnostic_screenshot(tab, f"error-{app_name}")
        raise


def _version_from_href(href: str) -> str | None:
    """
    APKMirror release URL'leri her zaman '...-<versiyon-tire-ile>-release/'
    kalıbını izler. Sayfa metninden (innerText) çıkarmaya çalışmak (badge,
    reklam vb. karışabildiği için) URL'den çıkarmaktan daha güvenilmez -
    bu yüzden önce URL'yi deniyoruz.
    """
    if not href:
        return None
    match = re.search(r"-(\d[\d]*(?:-\d+)+)-release", href)
    if not match:
        return None

    parts = match.group(1).split("-")
    # Bazı URL'lerde versiyon numarasına ekstra uzun bir versionCode
    # (ör. 932364120) yapışık geliyor - bu versiyonun parçası değil.
    # Android versionCode'lar genelde 7+ haneli olur.
    if len(parts) > 1 and len(parts[-1]) > 6:
        parts = parts[:-1]

    return ".".join(parts)


async def get_latest_listing(app_name: str) -> dict | None:
    app_config = APP_SITES.get(app_name)
    if not app_config:
        raise RuntimeError(f'Unknown appName "{app_name}" - not found in APP_SITES')

    browser = await get_browser()
    tab = browser.main_tab

    try:
        listing_url = f"https://www.apkmirror.com/apk/{app_config['org']}/{app_config['slug']}/"
        print("🌐 LISTING:", listing_url)

        js = """
        (() => {
            const links = Array.from(document.querySelectorAll("a[href*='-release/']")).slice(0, 15);
            return links.map(link => {
                const row = link.closest('div, li, tr') || link.parentElement;
                const text = row ? row.innerText : link.innerText;
                return { href: link.href, text: text || '' };
            });
        })()
        """

        candidates = []
        for attempt in range(3):
            await _goto(tab, listing_url, wait=1.5 + attempt, label="app-listing")
            candidates = await tab.evaluate(js)
            if candidates:
                break
            print(f"⚠️ Liste sayfasında link bulunamadı, tekrar deneniyor ({attempt + 1}/3)...")

        if not candidates:
            await _save_diagnostic_screenshot(tab, f"no-listing-{app_name}")
            return None

        # İlk bulunan link her zaman doğru olmayabilir (reklam, ilgili uygulama
        # linki vb. karışabilir) - versiyon çıkarılabilen İLK adayı kullan.
        for item in candidates:
            href = item.get("href") if isinstance(item, dict) else None
            text = item.get("text", "") if isinstance(item, dict) else ""

            version = _version_from_href(href)
            if not version:
                match = re.search(r"\d+(?:\.\d+)+", text)
                version = match.group(0) if match else None

            if version:
                return {"version": version, "href": href}

        await _save_diagnostic_screenshot(tab, f"no-version-{app_name}")
        return None

    except Exception:
        await _save_diagnostic_screenshot(tab, f"error-listing-{app_name}")
        raise
