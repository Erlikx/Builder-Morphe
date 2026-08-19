import asyncio
import json
import random
import re
import shutil
import time
from pathlib import Path

import zendriver as zd
from zendriver import cdp

from ..apk.versions import to_apkmirror_version
from .. import log
from .. import retry

APP_SITES = {
    "youtube": {"org": "google-inc", "slug": "youtube"},
    "youtube-music": {"org": "google-inc", "slug": "youtube-music"},
    "reddit": {"org": "reddit-inc", "slug": "reddit"},
    "twitter": {"org": "x-corp", "slug": "twitter", "release_slug": "x"},
    "instagram": {"org": "instagram", "slug": "instagram"},
    "gboard": {"org": "google-inc", "slug": "gboard", "release_slug": "gboard-the-google-keyboard"},
    "speedtest": {"org": "ookla", "slug": "speedtest"},
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
    "waze": {"org": "waze", "slug": "waze-gps-maps-traffic-alerts-live-navigation", "release_slug": "waze-navigation-live-traffic"},
    "proton-pass": {"org": "proton-technologies-ag", "slug": "proton-pass-password-manager"},
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36"

DIAGNOSTICS_DIR = Path(__file__).resolve().parent.parent.parent / "diagnostics"

_CHALLENGE_MARKERS = [
    "just a moment",
    "checking your browser",
    "attention required! | cloudflare",
    "verify you are human",
    "cf-browser-verification",
    "cf_chl_",
    "ddos protection by cloudflare",
]

_shared_browser = None
_downloads_ready = False
_challenge_hits = 0
_cooldown_until = 0.0


async def _jitter_sleep(base: float, spread: float = 0.6) -> None:
    await asyncio.sleep(base + random.uniform(0, spread))


async def get_browser():
    global _shared_browser

    if _shared_browser is not None:
        return _shared_browser

    async def _start(_attempt: int):
        chrome_path = (
            shutil.which("google-chrome-stable")
            or shutil.which("google-chrome")
            or shutil.which("chromium-browser")
            or shutil.which("chromium")
        )

        log.info(f"Launching browser at: {chrome_path or '(auto-detect, none found by shutil.which)'}")

        return await zd.start(
            headless=True,
            sandbox=False,
            browser_executable_path=chrome_path,
            browser_connection_timeout=10.0,
            browser_connection_max_tries=10,
            browser_args=[
                "--headless=new",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                f"--user-agent={USER_AGENT}",
            ],
        )

    _shared_browser = await retry.retry_async(
        _start,
        retries=6,
        delay_fn=lambda a: retry.linear_delay(a, base=1.5, cap=8.0),
        label="Could not start browser",
    )
    return _shared_browser


async def close_browser():
    global _shared_browser, _downloads_ready
    if _shared_browser is not None:
        try:
            await _shared_browser.stop()
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
        log.warn(f"set_download_behavior failed (will still try to proceed): {e}")


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
        log.info(f"Diagnostic screenshot saved: {path}")
    except Exception as e:
        log.warn(f"Could not capture screenshot: {e}")


async def _apply_global_cooldown():
    now = time.monotonic()
    if now < _cooldown_until:
        remaining = _cooldown_until - now
        log.wait(f"Global cooldown active, waiting {remaining:.0f}s...")
        await asyncio.sleep(remaining)


async def _goto(tab, url: str, wait: float = 1.2, challenge_retries: int = 3, label: str = "page"):
    global _challenge_hits, _cooldown_until

    await _apply_global_cooldown()

    for attempt in range(challenge_retries + 1):
        await tab.get(url)
        await _jitter_sleep(wait)

        if await _is_challenge_page(tab):
            _challenge_hits += 1
            cooldown_len = min(15.0 * (2 ** (_challenge_hits - 1)), 120.0)
            _cooldown_until = time.monotonic() + cooldown_len

            if attempt < challenge_retries:
                log.warn(
                    f"Cloudflare challenge detected ({label}), cooling down {cooldown_len:.0f}s "
                    f"before retrying (challenge #{_challenge_hits} this run)..."
                )
                await asyncio.sleep(cooldown_len)
                continue

            log.warn(f"Cloudflare challenge still present ({label}), proceeding anyway...")
            await _save_diagnostic_screenshot(tab, f"cloudflare-{label}")

        return


async def _row_count(tab) -> int:
    try:
        result = await tab.evaluate("document.querySelectorAll('.variants-table .table-row').length")
        return int(result or 0)
    except Exception:
        return 0


async def _is_404_page(tab) -> bool:
    try:
        content = await tab.evaluate("document.title + ' ' + (document.body.innerText || '').slice(0, 300)")
    except Exception:
        return False
    if not content:
        return False
    lowered = content.lower()
    return "404" in lowered and ("whoops" in lowered or "could not be found" in lowered or "not be found" in lowered)


async def _page_exists(tab, url: str) -> bool:
    try:
        await _goto(tab, url, wait=1.0, label="direct-try")
        if await _is_404_page(tab):
            return False
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
        log.search(f"TRY: {candidate}")
        if await _page_exists(tab, candidate):
            return candidate

    log.search("No direct match, scanning app listing page...")
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


async def _dump_variant_rows_for_debug(tab):
    js = """
    (() => {
        const rows = document.querySelectorAll('.table-row');
        const scopedRows = document.querySelectorAll('.variants-table .table-row');
        return JSON.stringify({
            rowCount: rows.length,
            scopedRowCount: scopedRows.length,
            is404: /404/.test(document.title) || /could not be found/i.test(document.body.innerText || ''),
            sample: Array.from(rows).slice(0, 20).map(row => {
                const cells = row.querySelectorAll('.table-cell');
                return {
                    cellCount: cells.length,
                    name: cells[0] ? cells[0].innerText.trim().slice(0, 60) : null,
                    arch: cells[1] ? cells[1].innerText.trim() : null,
                    dpi: cells[3] ? cells[3].innerText.trim() : null,
                };
            }),
        });
    })()
    """
    try:
        raw = await tab.evaluate(js)
        info = json.loads(raw) if isinstance(raw, str) else raw
        log.info(
            f"Debug: page has {info.get('rowCount', '?')} .table-row elements "
            f"({info.get('scopedRowCount', '?')} of them inside the real .variants-table), "
            f"is404: {info.get('is404', '?')}"
        )
        for i, row in enumerate(info.get("sample", [])):
            log.info(f"   [{i}] cells={row.get('cellCount')} name={row.get('name')!r} arch={row.get('arch')!r} dpi={row.get('dpi')!r}")
    except Exception as e:
        log.warn(f"Could not produce debug dump: {e}")


async def _extract_variant_url(tab, force_build: str | None, app_name: str) -> str | None:
    js = f"""
    (() => {{
        const rows = document.querySelectorAll('.variants-table .table-row');
        const candidates = [null, null, null, null, null, null];
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
            if (!isTargetArch) continue;

            const isNodpi = dpiText === '' || dpiText.includes('nodpi');
            const isAnydpi = dpiText.includes('anydpi');

            let slot;
            if (isNodpi) slot = isBundle ? 3 : 0;
            else if (isAnydpi) slot = isBundle ? 4 : 1;
            else slot = isBundle ? 5 : 2;

            if (!candidates[slot]) candidates[slot] = link.href;
        }}

        return candidates.find(c => c) || null;
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

    out_dir = Path(__file__).resolve().parent.parent.parent / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)

    browser = await get_browser()
    tab = browser.main_tab

    try:
        await _enable_downloads(tab, out_dir)

        list_url = await _resolve_list_url(tab, app_config, version)
        log.info(f"LIST: {list_url}")

        variant_url = None
        for attempt in range(4):
            await _goto(tab, list_url, wait=1.5 + attempt * 1.0, label="list-page")
            variant_url = await _extract_variant_url(tab, force_build, app_name)
            if variant_url:
                break
            log.warn(f"No matching row found on page, retrying ({attempt + 1}/4)...")

        if not variant_url:
            await _dump_variant_rows_for_debug(tab)
            await _save_diagnostic_screenshot(tab, f"no-variant-{app_name}")
            raise RuntimeError("No matching variant found on APKMirror")
        if variant_url.startswith("/"):
            variant_url = "https://www.apkmirror.com" + variant_url

        log.info(f"VARIANT: {variant_url}")

        await _goto(tab, variant_url, wait=1.2, label="variant-page")

        existing_before = {f.name for f in out_dir.iterdir() if f.is_file()}

        log.browser("Clicking main download button...")
        await tab.evaluate("document.querySelector('a.downloadButton')?.click()")

        downloaded = await _wait_for_download(out_dir, existing_before, timeout=20)

        if not downloaded:
            log.warn("Direct download did not start, waiting for confirm page...")
            await _jitter_sleep(1.5)

            final_href = await tab.evaluate(
                "(() => { const el = document.querySelector('#download-link'); return el ? el.getAttribute('href') : null; })()"
            )

            if final_href:
                log.browser("Clicking final download link...")
                await tab.evaluate("document.querySelector('#download-link')?.click()")
                downloaded = await _wait_for_download(out_dir, existing_before, timeout=60)

        if not downloaded:
            current_url = await tab.evaluate("location.href")
            current_title = await tab.evaluate("document.title")
            log.error(f"Download did not start. Current page: {current_title!r} @ {current_url}")
            await _save_diagnostic_screenshot(tab, f"no-download-{app_name}")
            raise RuntimeError("Download did not start / file not detected (CDP download).")

        size = downloaded.stat().st_size
        if size < 1024:
            raise RuntimeError(f"Downloaded file too small ({size} bytes)")

        log.success(f"DONE: {downloaded} ({size / 1024 / 1024:.2f} MB)")
        return str(downloaded)

    except Exception:
        await _save_diagnostic_screenshot(tab, f"error-{app_name}")
        raise


def _version_from_href(href: str) -> str | None:
    if not href:
        return None
    match = re.search(r"-(\d[\d]*(?:-\d+)+)-release", href)
    if not match:
        return None

    return match.group(1).replace("-", ".")


async def get_latest_listing(app_name: str) -> dict | None:
    app_config = APP_SITES.get(app_name)
    if not app_config:
        raise RuntimeError(f'Unknown appName "{app_name}" - not found in APP_SITES')

    browser = await get_browser()
    tab = browser.main_tab

    try:
        listing_url = f"https://www.apkmirror.com/apk/{app_config['org']}/{app_config['slug']}/"
        log.info(f"LISTING: {listing_url}")

        js = """
        (() => {
            const links = Array.from(document.querySelectorAll("a[href*='-release/']")).slice(0, 15);
            return JSON.stringify(links.map(link => {
                const row = link.closest('div, li, tr') || link.parentElement;
                const text = row ? row.innerText : link.innerText;
                return { href: link.href, text: text || '' };
            }));
        })()
        """

        candidates = []
        for attempt in range(4):
            await _goto(tab, listing_url, wait=2.5 + attempt * 1.2, label="app-listing")
            raw = await tab.evaluate(js)
            try:
                candidates = json.loads(raw) if isinstance(raw, str) else (raw or [])
            except Exception as e:
                log.warn(f"Could not parse listing data as JSON: {e}")
                candidates = []
            if candidates:
                break
            log.warn(f"No link found on listing page, retrying ({attempt + 1}/4)...")

        if not candidates:
            await _save_diagnostic_screenshot(tab, f"no-listing-{app_name}")
            return None

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
