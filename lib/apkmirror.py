import asyncio
import random
import os
from pathlib import Path
from playwright.async_api import async_playwright, Page
from versions import to_apkmirror_version

REALISTIC_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

APP_SITES = {
    "youtube": {"org": "google-inc", "slug": "youtube"},
    "youtube-music": {"org": "google-inc", "slug": "youtube-music"},
    "reddit": {"org": "reddit-inc", "slug": "reddit"},
    "twitter": {"org": "x-corp", "slug": "twitter", "releaseSlug": "x"},
    "instagram": {"org": "instagram", "slug": "instagram-instagram", "releaseSlug": "instagram"},
    "niagara-launcher": {"org": "mellowdrop-studio", "slug": "niagara-launcher-🔹-fresh-clean", "releaseSlug": "niagara-launcher-‧-home-screen"},
    "github": {"org": "github", "slug": "github-2", "releaseSlug": "github"},
    "smart-launcher": {"org": "smart-launcher-team", "slug": "smart-launcher", "releaseSlug": "smart-launcher-6-‧-home-screen"},
    "pydroid3": {"org": "lider-soft-kz", "slug": "pydroid-3-ide-for-python-3"},
    "brave": {"org": "brave-software", "slug": "brave-browser", "releaseSlug": "brave-private-web-browser-vpn"},
    "gboard": {"org": "google-inc", "slug": "gboard"},
    "speedtest": {"org": "ookla", "slug": "speedtest"},
    "solid-explorer": {"org": "neatbytes", "slug": "solid-explorer-file-manager"},
    "wps-office": {"org": "wps-software-pte-ltd", "slug": "wps-office-pdf", "releaseSlug": "wps-office-pdf-word-sheet"}
}

LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--no-sandbox",
    "--disable-setuid-sandbox",
]


def _new_context_args(viewport: dict) -> dict:
    return {
        "viewport": viewport,
        "user_agent": REALISTIC_UA,
        "locale": "en-US",
        "timezone_id": "America/New_York",
        "color_scheme": "light",
        "java_script_enabled": True,
    }


async def _is_cloudflare(page: Page) -> bool:
    try:
        return await page.evaluate("""() => {
            const t = (document.body && document.body.innerText) || '';
            const turnstile = !!document.querySelector("iframe[src*='challenges.cloudflare.com']");
            const challenge = !!document.querySelector("#challenge-running, .cf-browser-verification, #cf-please-wait, #challenge-form, .main-content > #challenge-form");
            const txt = /just a moment|checking your browser|verify you are human|checking if the site connection is secure|attention required|one more step/i.test(t);
            const noRows = document.querySelectorAll('.table-row').length === 0;
            return turnstile || challenge || (txt && noRows);
        }""")
    except Exception:
        return False


async def _wait_cloudflare(page: Page, max_wait: float = 35.0):
    loop = asyncio.get_event_loop()
    end = loop.time() + max_wait
    while loop.time() < end:
        if not await _is_cloudflare(page):
            return
        await asyncio.sleep(2.0)


async def page_exists(page: Page, url: str) -> bool:
    for _ in range(2):
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            if not response or response.status == 404:
                return False
            if response.status == 403:
                await asyncio.sleep(random.uniform(3.0, 5.0))
                await _wait_cloudflare(page)
                response = await page.reload(wait_until="domcontentloaded", timeout=20000)
                if response and response.status == 403:
                    return False
            await asyncio.sleep(random.uniform(2.0, 3.5))
            await _wait_cloudflare(page)
            try:
                await page.wait_for_selector(".table-row", timeout=20000)
                return True
            except Exception:
                await page.reload(wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(random.uniform(2.5, 4.0))
                await _wait_cloudflare(page)
                await page.wait_for_selector(".table-row", timeout=20000)
                return True
        except Exception:
            await asyncio.sleep(random.uniform(2.5, 4.5))
    return False


async def _dump_debug_html(page: Page, label: str):
    try:
        debug_dir = Path(__file__).parent.parent / "downloads" / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        safe_label = "".join(c if c.isalnum() else "_" for c in label)[:80]
        out_path = debug_dir / f"{safe_label}.html"
        html = await page.content()
        out_path.write_text(html, encoding="utf-8")
        print(f"🩺 Debug HTML kaydedildi: {out_path}")
    except Exception as dump_err:
        print(f"⚠️ Debug HTML kaydedilemedi: {dump_err}")


async def _wait_for_any_selector(page: Page, selectors: list[str], timeout: int = 20000) -> str:
    per_selector_timeout = max(timeout // len(selectors), 3000)
    last_err = None
    for sel in selectors:
        try:
            await page.wait_for_selector(sel, timeout=per_selector_timeout)
            return sel
        except Exception as e:
            last_err = e
            continue
    raise last_err or Exception(f"Hiçbir selector eşleşmedi: {selectors}")


async def _goto_and_wait(page: Page, url: str, selector: str, tries: int = 4, settle: float = 3.0, timeout: int = 45000):
    last = None
    for i in range(tries):
        try:
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if response and response.status == 403:
                await _wait_cloudflare(page, max_wait=20.0)
                await page.reload(wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(random.uniform(settle, settle + 2.0))
            await _wait_cloudflare(page)
            await page.wait_for_selector(selector, timeout=timeout)
            return
        except Exception as e:
            last = e
            print(f"🔄 '{selector}' beklenemedi, CF/retry ({i + 1}/{tries})...")
            try:
                await page.reload(wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(random.uniform(3.0, 5.0))
                await _wait_cloudflare(page)
                await page.wait_for_selector(selector, timeout=timeout)
                return
            except Exception as e2:
                last = e2
                await asyncio.sleep(random.uniform(3.0, 6.0))
    await _dump_debug_html(page, f"goto_and_wait_failed_{selector}")
    raise last


async def resolve_list_url(page: Page, app_config: dict, version: str) -> str:
    version_slug = to_apkmirror_version(version)
    name_part = app_config.get("releaseSlug", app_config["slug"])
    folder_url = f"https://www.apkmirror.com/apk/{app_config['org']}/{app_config['slug']}"

    candidates = [
        f"{folder_url}/{name_part}-{version_slug}-release/",
        f"{folder_url}/{name_part}-{version_slug}-release-0-release/",
        f"{folder_url}/{name_part}-{version_slug}-beta-0-release/",
        f"{folder_url}/{name_part}-{version_slug}-beta-1-release/"
    ]

    for candidate in candidates:
        print(f"🔎 TRY: {candidate}")
        if await page_exists(page, candidate):
            return candidate

    print("⚠️ No direct match, scanning app listing page...")
    listing_url = f"{folder_url}/"
    await _goto_and_wait(page, listing_url, "a[href*='-release/']", tries=2, timeout=20000)

    found_url = await page.evaluate("""(slugPart) => {
        const links = Array.from(document.querySelectorAll("a[href*='-release/']"));
        const match = links.find(a => a.getAttribute("href").includes(slugPart));
        return match ? match.href : null;
    }""", f"-{version_slug}-")

    if not found_url:
        raise Exception(f"No APKMirror release page found for version {version}")
    return found_url


async def download_apk(version: str, app_name: str = "youtube", force_build: str | None = None) -> str:
    async with async_playwright() as p:
        viewport = {"width": random.randint(1200, 1920), "height": random.randint(800, 1080)}

        browser = await p.chromium.launch(headless=True, args=LAUNCH_ARGS)
        context = await browser.new_context(
            **_new_context_args(viewport),
            accept_downloads=True,
        )
        page = await context.new_page()

        try:
            app_config = APP_SITES.get(app_name)
            if not app_config:
                raise Exception(f'Unknown appName "{app_name}" - not found in APP_SITES')

            list_url = await resolve_list_url(page, app_config, version)
            print(f"🌐 LIST: {list_url}")

            await _goto_and_wait(page, list_url, ".table-row", tries=3, timeout=30000)

            variant_url = await page.evaluate("""({ targetBuild, app }) => {
                const rows = document.querySelectorAll(".table-row");
                let standaloneNodpi = null, standaloneAnyDpi = null, bundleNodpi = null, bundleAnyDpi = null;
                const allowedArchs = ["universal", "evrensel", "noarch", "arm64-v8a", "arm64-v8a + armeabi-v7a", "arm64-v8a + armeabi"];

                for (const row of rows) {
                    const cells = row.querySelectorAll(".table-cell");
                    if (cells.length < 4) continue;
                    const link = cells[0].querySelector("a.accent_color") || cells[0].querySelector("a[href*='/apk/']");
                    if (!link) continue;
                    if (targetBuild && !cells[0].innerText.includes(targetBuild)) continue;

                    const badge = cells[0].querySelector(".apkm-badge");
                    const isBundle = badge ? (badge.innerText.toUpperCase().includes("BUNDLE") || badge.innerText.toUpperCase().includes("PAKET")) : false;
                    if (app === "instagram" && !isBundle) continue;

                    const archText = cells[1].innerText.trim().toLowerCase();
                    const dpiText = cells[3].innerText.trim().toLowerCase();
                    const isTargetArch = archText === "" || allowedArchs.some(arch => archText.includes(arch));
                    const isTargetDpi = dpiText === "" || dpiText.includes("nodpi") || dpiText.includes("anydpi") || /\\d+-640dpi/.test(dpiText);

                    if (isTargetArch && isTargetDpi) {
                        if (!isBundle) {
                            if (dpiText.includes("nodpi")) standaloneNodpi = link.href;
                            else standaloneAnyDpi = link.href;
                        } else {
                            if (dpiText.includes("nodpi")) bundleNodpi = link.href;
                            else bundleAnyDpi = link.href;
                        }
                    }
                }
                return standaloneNodpi || standaloneAnyDpi || bundleNodpi || bundleAnyDpi;
            }""", {"targetBuild": force_build, "app": app_name})

            if not variant_url:
                await _dump_debug_html(page, "no_variant_found")
                raise Exception("No matching variant found on APKMirror")

            print(f"➡️ VARIANT: {variant_url}")
            await _goto_and_wait(page, variant_url, "a.downloadButton", tries=3, timeout=30000)

            print("⬇️ Resolving download URL...")
            try:
                btn_selector = await _wait_for_any_selector(
                    page, ["a.downloadButton", "a[href*='/download/']", "a:has-text('Download APK')"]
                )
            except Exception:
                await _dump_debug_html(page, "download_button_not_found")
                raise Exception("İndirme butonu bulunamadı")

            btn_href = await page.get_attribute(btn_selector, "href")
            if not btn_href:
                raise Exception("Download button has no href")
            if not btn_href.startswith("http"):
                btn_href = "https://www.apkmirror.com" + btn_href

            await _goto_and_wait(page, btn_href, "a#download-link", tries=3, timeout=30000)

            print("⬇️ Clicking final download link...")
            out_dir = Path(__file__).parent.parent / "downloads"
            out_dir.mkdir(parents=True, exist_ok=True)

            try:
                final_selector = await _wait_for_any_selector(
                    page, ["a#download-link", "a[href*='.apk']", "a:has-text('here')"]
                )
            except Exception:
                await _dump_debug_html(page, "final_download_link_not_found")
                raise Exception("Son indirme linki bulunamadı")

            async with page.expect_download(timeout=120000) as dl_info:
                await page.click(final_selector)
            download = await dl_info.value
            fname = download.suggested_filename
            if callable(fname):
                fname = fname()
            file_path = out_dir / fname
            await download.save_as(str(file_path))

            print(f"📦 DONE: {file_path}")
            return str(file_path)

        finally:
            await browser.close()


async def get_latest_listing(app_name: str) -> dict:
    app_config = APP_SITES.get(app_name)
    if not app_config:
        raise Exception(f'Unknown appName "{app_name}"')

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=LAUNCH_ARGS)
        context = await browser.new_context(**_new_context_args({"width": 1366, "height": 768}))
        page = await context.new_page()

        try:
            listing_url = f"https://www.apkmirror.com/apk/{app_config['org']}/{app_config['slug']}/"
            print(f"🌐 LISTING: {listing_url}")
            await page.goto(listing_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1.5, 2.5))
            await _wait_cloudflare(page)

            result = await page.evaluate("""() => {
                const link = document.querySelector("a[href*='-release/']");
                if (!link) return null;
                const row = link.closest("div, li, tr") || link.parentElement;
                const text = row ? row.innerText : link.innerText;
                const versionMatch = text.match(/\\d+(?:\\.\\d+)+(?:\\s+build\\s+\\d+)?/);
                return {
                    version: versionMatch ? versionMatch[0] : null,
                    href: link.href
                };
            }""")
            return result or {"version": "latest", "href": listing_url}
        finally:
            await browser.close()
