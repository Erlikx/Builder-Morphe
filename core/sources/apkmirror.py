import asyncio
import contextlib
import json
import random
import re
import time
from pathlib import Path
from typing import Any

from camoufox import DefaultAddons
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from tenacity import AsyncRetrying, retry, retry_if_exception_type, stop_after_attempt
from tenacity.stop import stop_base
from tenacity.wait import wait_base

from .. import log
from .. import retry as retry_conf
from ..apk.versions import to_apkmirror_version

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
    "proton-pass": {"org": "proton-technologies-ag", "slug": "proton-pass-password-manager"},
    "notesnook": {
        "org": "streetwriters-private-limited",
        "slug": "notesnook-private-notes-app",
        "release_slug": "notesnook-secure-private-notes",
    },
    "termius": {
        "org": "termius-corporation",
        "slug": "termius-ssh-telnet-client",
        "release_slug": "termius-modern-ssh-client",
    },
}

DIAGNOSTICS_DIR = Path(__file__).resolve().parent.parent.parent / "diagnostics"

RESOLVE_BUDGET_SECONDS = 300.0

_CHALLENGE_MARKERS = [
    "just a moment",
    "checking your browser",
    "attention required! | cloudflare",
    "verify you are human",
    "cf-browser-verification",
    "cf_chl_",
    "ddos protection by cloudflare",
    # Newer Cloudflare "Managed Challenge" / Turnstile interstitial. Its
    # "Verify you are human" checkbox text lives inside a cross-origin
    # iframe, so it never shows up in document.body.innerText - only the
    # outer wrapper text below does. Without these, this page type is
    # invisible to _is_challenge_page() and gets treated as a normal
    # (button-less) page instead of a challenge to cool down and retry.
    "performing security verification",
    "verifies you are not a bot",
]

_camoufox_stack: contextlib.AsyncExitStack | None = None
_shared_browser = None
_shared_page: Page | None = None
_challenge_hits = 0
_cooldown_until = 0.0


async def _jitter_sleep(base: float, spread: float = 0.6) -> None:
    await asyncio.sleep(base + random.uniform(0, spread))


@retry(
    stop=stop_after_attempt(6),
    wait=retry_conf.incrementing(start=1.5, increment=1.5, max=8.0),
    before_sleep=retry_conf.before_sleep("Could not start browser"),
    reraise=True,
)
async def _start_browser():
    log.info("Launching Camoufox (Firefox)...")
    stack = contextlib.AsyncExitStack()
    # humanize=True adds realistic, non-linear cursor movement on clicks;
    # everything else about the Firefox fingerprint (UA, navigator
    # properties, ...) is generated and kept internally consistent by
    # Camoufox itself, so there's no manual UA-building step here anymore.
    #
    # exclude_addons=[UBO]: Camoufox bundles uBlock Origin by default. On
    # APKMirror that backfires - it blocks the ad slots on the variant
    # page, APKMirror's own ad-blocker check notices and swaps in a
    # "Whoa there! It looks like you're using an ad blocker, wait 15 more
    # sec" panel instead of the real download link, and the click/`#download-link`
    # logic below (which expects the normal fast confirm flow) never finds
    # anything to click. Dropping the bundled adblocker avoids tripping
    # that wall in the first place, and also removes one more network
    # fetch (the addon download) from browser startup.
    browser = await stack.enter_async_context(
        AsyncCamoufox(headless=True, humanize=True, exclude_addons=[DefaultAddons.UBO])
    )
    return stack, browser


async def get_browser():
    global _camoufox_stack, _shared_browser
    if _shared_browser is not None:
        return _shared_browser
    _camoufox_stack, _shared_browser = await _start_browser()
    return _shared_browser


async def get_page() -> Page:
    """A single shared page for the whole run, the same way the old code
    reused one `main_tab` - opening a fresh `browser.new_page()` per call
    would each get its own isolated context and lose the Cloudflare
    clearance cookie between e.g. a listing lookup and the download that
    follows it."""
    global _shared_page
    browser = await get_browser()
    if _shared_page is None or _shared_page.is_closed():
        _shared_page = await browser.new_page()
    return _shared_page


async def close_browser():
    global _camoufox_stack, _shared_browser, _shared_page
    if _camoufox_stack is not None:
        with contextlib.suppress(Exception):
            await _camoufox_stack.aclose()
        _camoufox_stack = None
        _shared_browser = None
        _shared_page = None


async def _is_challenge_page(page: Page) -> bool:
    try:
        content = await page.evaluate(
            "(document.title + ' ' + document.body.innerText.slice(0, 500)).toLowerCase()"
        )
    except Exception:
        return False
    if not content:
        return False
    return any(marker in content for marker in _CHALLENGE_MARKERS)


async def _save_diagnostic_screenshot(page: Page, label: str):
    try:
        DIAGNOSTICS_DIR.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        path = DIAGNOSTICS_DIR / f"{label}-{ts}.png"
        await page.screenshot(path=str(path))
        log.info(f"Diagnostic screenshot saved: {path}")
    except Exception as e:
        log.warn(f"Could not capture screenshot: {e}")


async def _apply_global_cooldown():
    now = time.monotonic()
    if now < _cooldown_until:
        remaining = _cooldown_until - now
        log.wait(f"Global cooldown active, waiting {remaining:.0f}s...")
        await asyncio.sleep(remaining)


class _ChallengePresent(Exception):
    """Raised internally when the page we just loaded is a Cloudflare
    challenge. Carries the escalated cooldown so the wait/stop strategies
    below don't have to recompute (and re-escalate) it themselves."""

    def __init__(self, cooldown: float):
        super().__init__("Cloudflare challenge page detected")
        self.cooldown = cooldown


def _register_challenge() -> float:
    """Escalate the cooldown shared by every future call to `_goto` for the
    rest of this run (mirrors the old module-level bookkeeping), and return
    how long this particular escalation is."""
    global _challenge_hits, _cooldown_until
    _challenge_hits += 1
    cooldown = min(15.0 * (2 ** (_challenge_hits - 1)), 120.0)
    _cooldown_until = time.monotonic() + cooldown
    return cooldown


class _ChallengeCooldownWait(wait_base):
    def __call__(self, retry_state) -> float:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        return exc.cooldown if isinstance(exc, _ChallengePresent) else 0.0


class _BudgetExceeded(stop_base):
    """Stop retrying once waiting out the next cooldown would blow the
    caller's overall per-version resolve budget."""

    def __init__(self, deadline: float | None):
        self.deadline = deadline

    def __call__(self, retry_state) -> bool:
        if self.deadline is None or retry_state.outcome is None:
            return False
        exc = retry_state.outcome.exception()
        cooldown = exc.cooldown if isinstance(exc, _ChallengePresent) else 0.0
        return time.monotonic() + cooldown >= self.deadline


async def _goto(
    page: Page,
    url: str,
    wait: float = 1.2,
    challenge_retries: int = 3,
    label: str = "page",
    deadline: float | None = None,
):
    await _apply_global_cooldown()

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(challenge_retries + 1) | _BudgetExceeded(deadline),
            wait=_ChallengeCooldownWait(),
            retry=retry_if_exception_type(_ChallengePresent),
            before_sleep=lambda rs: log.warn(
                f"Cloudflare challenge detected ({label}), cooling down "
                f"{(rs.next_action.sleep if rs.next_action else 0):.0f}s before retrying "
                f"(challenge #{_challenge_hits} this run)..."
            ),
            reraise=True,
        ):
            with attempt:
                await page.goto(url)
                await _jitter_sleep(wait)
                if await _is_challenge_page(page):
                    raise _ChallengePresent(_register_challenge())
    except _ChallengePresent:
        log.warn(f"Cloudflare challenge still present ({label}), proceeding anyway...")
        await _save_diagnostic_screenshot(page, f"cloudflare-{label}")


async def _row_count(page: Page) -> int:
    try:
        result = await page.evaluate("document.querySelectorAll('.variants-table .table-row').length")
        return int(result or 0)
    except Exception:
        return 0


async def _is_404_page(page: Page) -> bool:
    try:
        content = await page.evaluate("document.title + ' ' + (document.body.innerText || '').slice(0, 300)")
    except Exception:
        return False
    if not content:
        return False
    lowered = content.lower()
    return "404" in lowered and (
        "whoops" in lowered or "could not be found" in lowered or "not be found" in lowered
    )


async def _page_exists(page: Page, url: str, deadline: float | None = None) -> bool:
    try:
        await _goto(page, url, wait=1.0, label="direct-try", deadline=deadline)
        if await _is_404_page(page):
            return False
        return (await _row_count(page)) > 0
    except Exception:
        return False


async def _has_download_button(page: Page) -> bool:
    try:
        result = await page.evaluate("document.querySelectorAll('a.downloadButton').length")
        return int(result or 0) > 0
    except Exception:
        return False


async def _resolve_list_url(page: Page, app_config: dict, version: str) -> tuple[str, bool]:
    version_slug = to_apkmirror_version(version)
    name_part = app_config.get("release_slug") or app_config["slug"]
    folder_url = f"https://www.apkmirror.com/apk/{app_config['org']}/{app_config['slug']}"
    deadline = time.monotonic() + RESOLVE_BUDGET_SECONDS

    release_slugs = [
        f"{name_part}-{version_slug}-release",
        f"{name_part}-{version_slug}-release-0-release",
        f"{name_part}-{version_slug}-beta-0-release",
        f"{name_part}-{version_slug}-beta-1-release",
    ]

    for slug in release_slugs:
        if time.monotonic() > deadline:
            break

        candidate = f"{folder_url}/{slug}/"
        log.search(f"TRY: {candidate}")
        if await _page_exists(page, candidate, deadline=deadline):
            return candidate, False

        if time.monotonic() > deadline:
            break

        direct_variant = f"{candidate}{name_part}-{version_slug}-android-apk-download/"
        log.search(f"TRY (single-variant direct): {direct_variant}")
        try:
            await _goto(page, direct_variant, wait=1.0, label="direct-variant-try", deadline=deadline)
            if not await _is_404_page(page) and await _has_download_button(page):
                return direct_variant, True
        except Exception:
            pass

    if time.monotonic() > deadline:
        await _save_diagnostic_screenshot(page, f"budget-exceeded-{app_config['slug']}")
        raise RuntimeError(
            f"Giving up on {app_config['slug']} v{version}: APKMirror kept challenge-walling every "
            f"attempt (exceeded {RESOLVE_BUDGET_SECONDS:.0f}s resolve budget)"
        )

    log.search("No direct match, scanning app listing page...")
    listing_url = f"{folder_url}/"

    slug_part = f"-{version_slug}-"
    js = f"""
    (() => {{
        const links = Array.from(document.querySelectorAll("a[href*='-release/']"));
        const match = links.find(a => {{
            const href = a.getAttribute('href');
            return href.includes({json.dumps(slug_part)}) && !href.includes('#');
        }});
        return match ? match.href : null;
    }})()
    """

    for attempt in range(2):
        if time.monotonic() > deadline:
            break
        await _goto(page, listing_url, wait=1.5 + attempt, label="listing-scan", deadline=deadline)
        found_url = await page.evaluate(js)
        if found_url:
            return found_url, False

    await _save_diagnostic_screenshot(page, f"no-match-{app_config['slug']}")
    raise RuntimeError(f"No APKMirror release page found for version {version}")


async def _dump_variant_rows_for_debug(page: Page):
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
        raw = await page.evaluate(js)
        info = json.loads(raw) if isinstance(raw, str) else raw
        log.info(
            f"Debug: page has {info.get('rowCount', '?')} .table-row elements "
            f"({info.get('scopedRowCount', '?')} of them inside the real .variants-table), "
            f"is404: {info.get('is404', '?')}"
        )
        for i, row in enumerate(info.get("sample", [])):
            log.info(
                f"   [{i}] cells={row.get('cellCount')} name={row.get('name')!r} "
                f"arch={row.get('arch')!r} dpi={row.get('dpi')!r}"
            )
    except Exception as e:
        log.warn(f"Could not produce debug dump: {e}")


async def _extract_variant_url(page: Page, force_build: str | None, app_name: str) -> str | None:
    js = f"""
    (() => {{
        const rows = document.querySelectorAll('.variants-table .table-row');
        const candidates = [null, null, null, null, null, null];
        const allowedArchs = [
            'universal', 'evrensel', 'noarch', 'arm64-v8a', 'arm64-v8a + armeabi-v7a', 'arm64-v8a + armeabi'
        ];
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
    return await page.evaluate(js)


async def _click_and_download(page: Page, selector: str, timeout_ms: float):
    """Arm Playwright's download listener, click, and return the Download -
    or None if nothing had started by timeout_ms (APKMirror sometimes shows
    an interstitial "confirm" page instead of downloading directly)."""
    try:
        async with page.expect_download(timeout=timeout_ms) as download_info:
            await page.click(selector)
        return await download_info.value
    except PlaywrightTimeoutError:
        return None


async def _attempt_download(page: Page):
    download = await _click_and_download(page, "a.downloadButton", timeout_ms=20_000)

    if download is None:
        log.warn("Direct download did not start, waiting for confirm page...")
        await _jitter_sleep(1.5)

        if await page.locator("#download-link").count() > 0:
            log.browser("Clicking final download link...")
            download = await _click_and_download(page, "#download-link", timeout_ms=60_000)

    if download is None:
        raise _ChallengePresent(_register_challenge())

    return download


async def download_apk(version: str, app_name: str = "youtube", force_build: str | None = None) -> str:
    app_config = APP_SITES.get(app_name)
    if not app_config:
        raise RuntimeError(f'Unknown appName "{app_name}" - not found in APP_SITES')

    out_dir = Path(__file__).resolve().parent.parent.parent / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)

    page = await get_page()

    try:
        list_url, is_final = await _resolve_list_url(page, app_config, version)
        log.info(f"LIST: {list_url}")

        if is_final:
            variant_url = list_url
            log.info(f"VARIANT: {variant_url} (single-variant release, page already loaded)")
        else:
            variant_url = None
            for attempt in range(4):
                await _goto(page, list_url, wait=1.5 + attempt * 1.0, label="list-page")
                variant_url = await _extract_variant_url(page, force_build, app_name)
                if variant_url:
                    break
                log.warn(f"No matching row found on page, retrying ({attempt + 1}/4)...")

            if not variant_url:
                await _dump_variant_rows_for_debug(page)
                await _save_diagnostic_screenshot(page, f"no-variant-{app_name}")
                raise RuntimeError("No matching variant found on APKMirror")
            if variant_url.startswith("/"):
                variant_url = "https://www.apkmirror.com" + variant_url

            log.info(f"VARIANT: {variant_url}")
            await _goto(page, variant_url, wait=1.2, label="variant-page")

        log.browser("Clicking main download button...")
        assert variant_url is not None
        download = None
        try:
            async for retry_attempt in AsyncRetrying(
                stop=stop_after_attempt(4),
                wait=_ChallengeCooldownWait(),
                retry=retry_if_exception_type(_ChallengePresent),
                before_sleep=lambda rs: log.warn(
                    f"Download click had no effect, cooling down "
                    f"{(rs.next_action.sleep if rs.next_action else 0):.0f}s before retrying "
                    f"(attempt #{_challenge_hits} this run)..."
                ),
                reraise=True,
            ):
                with retry_attempt:
                    if retry_attempt.retry_state.attempt_number > 1:
                        await _goto(page, variant_url, wait=1.2, label="variant-page-retry")
                        log.browser("Clicking main download button...")
                    download = await _attempt_download(page)
        except _ChallengePresent:
            pass

        if download is None:
            log.error(f"Download did not start. Current page: {(await page.title())!r} @ {page.url}")
            await _save_diagnostic_screenshot(page, f"no-download-{app_name}")
            raise RuntimeError("Download did not start / file not detected.")

        final_path = out_dir / download.suggested_filename
        await download.save_as(final_path)

        size = final_path.stat().st_size
        if size < 1024:
            raise RuntimeError(f"Downloaded file too small ({size} bytes)")

        log.success(f"DONE: {final_path} ({size / 1024 / 1024:.2f} MB)")
        return str(final_path)

    except Exception:
        await _save_diagnostic_screenshot(page, f"error-{app_name}")
        raise


def _version_from_href(href: str | None) -> str | None:
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

    page = await get_page()

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

        candidates: list[Any] = []
        for attempt in range(4):
            await _goto(page, listing_url, wait=2.5 + attempt * 1.2, label="app-listing")
            raw = await page.evaluate(js)
            try:
                candidates = json.loads(raw) if isinstance(raw, str) else (raw or [])
            except Exception as e:
                log.warn(f"Could not parse listing data as JSON: {e}")
                candidates = []
            if candidates:
                break
            log.warn(f"No link found on listing page, retrying ({attempt + 1}/4)...")

        if not candidates:
            await _save_diagnostic_screenshot(page, f"no-listing-{app_name}")
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

        await _save_diagnostic_screenshot(page, f"no-version-{app_name}")
        return None

    except Exception:
        await _save_diagnostic_screenshot(page, f"error-listing-{app_name}")
        raise
