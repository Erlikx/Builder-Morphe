import os
import re
import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

DOWNLOADS_DIR = Path(__file__).parent.parent / "downloads"

APP_SITES = {
    "youtube":          {"org": "google-inc",           "slug": "youtube"},
    "youtube-music":    {"org": "google-inc",           "slug": "youtube-music"},
    "reddit":           {"org": "reddit-inc",           "slug": "reddit"},
    "twitter":          {"org": "x-corp",               "slug": "twitter",           "releaseSlug": "x"},
    "instagram":        {"org": "instagram",            "slug": "instagram"},
    "github":           {"org": "github",               "slug": "github-2"},
    "niagara-launcher": {"org": "mellowdrop-studio",    "slug": "niagara-launcher-fresh-clean"},
    "pydroid3":         {"org": "lider-soft-kz",        "slug": "pydroid-3-ide-for-python-3"},
    "smart-launcher":   {"org": "smart-launcher-team",  "slug": "smart-launcher"},
    "wps-office":       {"org": "wps-software-pte-ltd", "slug": "wps-office-pdf"},
    "gboard":           {"org": "google-inc",           "slug": "gboard"},
    "speedtest":        {"org": "ookla",                "slug": "speedtest"},
    "solid-explorer":   {"org": "neatbytes",            "slug": "solid-explorer-file-manager"},
    "brave":            {"org": "brave-software",       "slug": "brave-browser"},
}

ALLOWED_ARCHS = {
    "universal", "evrensel", "noarch",
    "arm64-v8a",
    "arm64-v8a + armeabi-v7a",
    "arm64-v8a + armeabi",
}


def _human_delay(lo=1.5, hi=4.0):
    time.sleep(random.uniform(lo, hi))


def _scroll_page(page):
    page.evaluate("window.scrollBy(0, Math.floor(Math.random() * 400 + 100))")
    _human_delay(0.5, 1.5)


def _to_apkmirror_version(version: str) -> str:
    return version.replace(".", "-")


def _build_context(playwright):
    browser = playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--window-size=1280,900",
        ],
    )
    context = browser.new_context(
        viewport={"width": 1280, "height": 900},
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        locale="en-US",
        timezone_id="America/New_York",
        accept_downloads=True,
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "DNT":             "1",
        },
    )
    # Hide webdriver flag
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        window.chrome = { runtime: {} };
    """)
    return browser, context


def _safe_goto(page, url, retries=4):
    """Navigate with exponential backoff on failure."""
    for attempt in range(retries):
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            _scroll_page(page)
            return resp
        except PlaywrightTimeout:
            wait = (2 ** attempt) * 3 + random.uniform(0, 2)
            print(f"  ⏳ Timeout on attempt {attempt+1}, retrying in {wait:.1f}s…")
            time.sleep(wait)
    raise RuntimeError(f"Failed to load {url} after {retries} attempts")


def _page_has_rows(page, url):
    resp = page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    if not resp or resp.status == 404:
        return False
    _human_delay(1.0, 2.5)
    _scroll_page(page)
    try:
        page.wait_for_selector(".table-row", timeout=8_000)
        return True
    except PlaywrightTimeout:
        return False


def _resolve_list_url(page, app_cfg, version):
    slug = app_cfg["slug"]
    org  = app_cfg["org"]
    name = app_cfg.get("releaseSlug", slug)
    ver  = _to_apkmirror_version(version)
    base = f"https://www.apkmirror.com/apk/{org}/{slug}"

    candidates = [
        f"{base}/{name}-{ver}-release/",
        f"{base}/{name}-{ver}-release-0-release/",
        f"{base}/{name}-{ver}-beta-0-release/",
        f"{base}/{name}-{ver}-beta-1-release/",
    ]

    for url in candidates:
        print(f"  🔎 Trying: {url}")
        _human_delay(2.0, 4.5)
        if _page_has_rows(page, url):
            return url

    # Fall back: scan listing page
    print("  ⚠️  Direct match not found, scanning listing…")
    listing = f"{base}/"
    _safe_goto(page, listing)
    _human_delay(2.0, 3.5)

    found = page.evaluate(
        """(ver) => {
            const links = Array.from(document.querySelectorAll("a[href*='-release/']"));
            const m = links.find(a => a.getAttribute('href').includes(ver));
            return m ? m.href : null;
        }""",
        f"-{ver}-",
    )
    if not found:
        raise RuntimeError(f"No APKMirror release page found for version {version}")
    return found


def _pick_variant(page, app_name: str, force_build: str | None):
    """Return the href of the best-matching variant row."""
    return page.evaluate(
        """({ targetBuild, appName, allowedArchs }) => {
            const rows = document.querySelectorAll('.table-row');
            let standaloneNodpi = null, standaloneAny = null;
            let bundleNodpi    = null, bundleAny    = null;

            for (const row of rows) {
                const cells = row.querySelectorAll('.table-cell');
                if (cells.length < 4) continue;

                const link = cells[0].querySelector('a.accent_color');
                if (!link) continue;

                if (targetBuild && !cells[0].innerText.includes(targetBuild)) continue;

                const badge    = cells[0].querySelector('.apkm-badge');
                const isBundle = badge
                    ? (badge.innerText.toUpperCase().includes('BUNDLE') ||
                       badge.innerText.toUpperCase().includes('PAKET'))
                    : false;

                if (appName === 'instagram' && !isBundle) continue;

                const arch = cells[1].innerText.trim().toLowerCase();
                const dpi  = cells[3].innerText.trim().toLowerCase();

                const okArch = arch === '' ||
                    allowedArchs.some(a => arch.includes(a.toLowerCase()));
                const okDpi  = dpi === '' ||
                    dpi.includes('nodpi') ||
                    dpi.includes('anydpi') ||
                    /\\d+-640dpi/.test(dpi);

                if (okArch && okDpi) {
                    if (!isBundle) {
                        if (dpi.includes('nodpi')) standaloneNodpi = link.href;
                        else                        standaloneAny  = link.href;
                    } else {
                        if (dpi.includes('nodpi')) bundleNodpi = link.href;
                        else                        bundleAny   = link.href;
                    }
                }
            }
            return standaloneNodpi || standaloneAny || bundleNodpi || bundleAny;
        }""",
        {"targetBuild": force_build, "appName": app_name, "allowedArchs": list(ALLOWED_ARCHS)},
    )


def download_apk(version: str, app_name: str = "youtube", force_build: str | None = None) -> str:
    app_cfg = APP_SITES.get(app_name)
    if not app_cfg:
        raise ValueError(f"Unknown app: {app_name}")

    DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser, context = _build_context(pw)
        page = context.new_page()

        try:
            # ── 1. Find release listing page ──────────────────────────────
            list_url = _resolve_list_url(page, app_cfg, version)
            print(f"  🌐 List page: {list_url}")

            _safe_goto(page, list_url)
            _human_delay(2.5, 5.0)
            page.wait_for_selector(".table-row", timeout=30_000)
            _scroll_page(page)

            # ── 2. Pick the right variant ─────────────────────────────────
            variant_url = _pick_variant(page, app_name, force_build)
            if not variant_url:
                raise RuntimeError("No matching variant found on APKMirror")
            print(f"  ➡️  Variant: {variant_url}")

            _human_delay(2.0, 4.0)
            _safe_goto(page, variant_url)
            _human_delay(2.0, 4.5)
            page.wait_for_selector("a.downloadButton", timeout=30_000)
            _scroll_page(page)

            # ── 3. Download ───────────────────────────────────────────────
            _human_delay(1.5, 3.0)
            with page.expect_download(timeout=300_000) as dl_info:
                page.click("a.downloadButton")

            download = dl_info.value
            file_path = DOWNLOADS_DIR / download.suggested_filename
            download.save_as(str(file_path))
            print(f"  📦 Saved: {file_path}")
            return str(file_path)

        except Exception:
            # Fallback: try #download-link on variant page
            try:
                fallback_url = page.eval_on_selector("#download-link", "el => el.href")
                print(f"  ⚠️  Main download failed, trying fallback: {fallback_url}")
                _human_delay(2.0, 4.0)
                page2 = context.new_page()
                with page2.expect_download(timeout=300_000) as dl_info2:
                    page2.goto(fallback_url, wait_until="domcontentloaded")
                download2 = dl_info2.value
                file_path = DOWNLOADS_DIR / download2.suggested_filename
                download2.save_as(str(file_path))
                page2.close()
                print(f"  📦 Saved (fallback): {file_path}")
                return str(file_path)
            except Exception as e2:
                raise RuntimeError(f"APKMirror download failed: {e2}") from e2
        finally:
            browser.close()


def get_latest_listing(app_name: str) -> dict | None:
    app_cfg = APP_SITES.get(app_name)
    if not app_cfg:
        raise ValueError(f"Unknown app: {app_name}")

    org  = app_cfg["org"]
    slug = app_cfg["slug"]
    url  = f"https://www.apkmirror.com/apk/{org}/{slug}/"
    print(f"  🌐 Listing: {url}")

    with sync_playwright() as pw:
        browser, context = _build_context(pw)
        page = context.new_page()
        try:
            _safe_goto(page, url)
            _human_delay(2.0, 4.0)

            result = page.evaluate("""() => {
                const link = document.querySelector("a[href*='-release/']");
                if (!link) return null;
                const row   = link.closest('div, li, tr') || link.parentElement;
                const text  = row ? row.innerText : link.innerText;
                const match = text.match(/\\d+(?:\\.\\d+)+/);
                return { version: match ? match[0] : null, href: link.href };
            }""")
            return result
        finally:
            browser.close()
