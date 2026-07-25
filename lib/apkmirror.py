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

    retries = 6
    base_delay = 4.0
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
    return any(marker in content for
