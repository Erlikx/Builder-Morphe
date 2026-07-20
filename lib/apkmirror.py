import asyncio
import random
import os
from pathlib import Path
from playwright.async_api import async_playwright, Page
from versions import to_apkmirror_version

_STEALTH_MODE = None
try:
    from playwright_stealth import Stealth
    _STEALTH_MODE = "v2"
except ImportError:
    try:
        from playwright_stealth import stealth_async
        _STEALTH_MODE = "v1"
    except ImportError:
        _STEALTH_MODE = None

APP_SITES = {
    "youtube": {"org": "google-inc", "slug": "youtube"},
    "youtube-music": {"org": "google-inc", "slug": "youtube-music"},
    "reddit": {"org": "reddit-inc", "slug": "reddit"},
    "twitter": {"org": "x-corp", "slug": "twitter", "releaseSlug": "x"},
    "instagram": {"org": "instagram", "slug": "instagram-instagram"},
    "niagara-launcher": {"org": "mellowdrop-studio", "slug": "niagara-launcher-🔹-fresh-clean", "releaseSlug": "niagara-launcher-\u2027-home-screen"},
    "github": {"org": "github", "slug": "github-2"},
    "smart-launcher": {"org": "smart-launcher-team", "slug": "smart-launcher", "releaseSlug": "smart-launcher-6-home-screen"},
    "pydroid3": {"org": "lider-soft-kz", "slug": "pydroid-3-ide-for-python-3"},
    "brave": {"org": "brave-software", "slug": "brave-browser", "releaseSlug": "brave-private-web-browser-vpn"},
    "gboard": {"org": "google-inc", "slug": "gboard"},
    "speedtest": {"org": "ookla", "slug": "speedtest"},
    "solid-explorer": {"org": "neatbytes", "slug": "solid-explorer-file-manager"},
    "wps-office": {"org": "wps-software-pte-ltd", "slug": "wps-office-pdf"}
}

async def setup_stealth(page: Page):
    if _STEALTH_MODE == "v2":
        try:
            await Stealth().apply_stealth_async(page)
        except Exception:
            pass
    elif _STEALTH_MODE == "v1":
        try:
            await stealth_async(page)
        except Exception:
            pass
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
        Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
    """)

async def page_exists(page: Page, url: str) -> bool:
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        if not response or response.status == 404:
            return False
        has_rows = await page.query_selector(".table-row")
        return bool(has_rows)
    except Exception:
        return False

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
    await page.goto(listing_url, wait_until="domcontentloaded")
    await asyncio.sleep(random.uniform(1.0, 2.5))

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
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
        ]

        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            viewport=viewport,
            user_agent=random.choice(user_agents),
            accept_downloads=True
        )
        page = await context.new_page()
        await setup_stealth(page)

        try:
            app_config = APP_SITES.get(app_name)
            if not app_config:
                raise Exception(f'Unknown appName "{app_name}" - not found in APP_SITES')

            list_url = await resolve_list_url(page, app_config, version)
            print(f"🌐 LIST: {list_url}")

            await page.goto(list_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1.5, 3.0))
            await page.wait_for_selector(".table-row", timeout=45000)

            variant_url = await page.evaluate("""({ targetBuild, app }) => {
                const rows = document.querySelectorAll(".table-row");
                let standaloneNodpi = null, standaloneAnyDpi = null, bundleNodpi = null, bundleAnyDpi = null;
                const allowedArchs = ["universal", "evrensel", "noarch", "arm64-v8a", "arm64-v8a + armeabi-v7a", "arm64-v8a + armeabi"];

                for (const row of rows) {
                    const cells = row.querySelectorAll(".table-cell");
                    if (cells.length < 4) continue;
                    const link = cells[0].querySelector("a.accent_color");
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
                raise Exception("No matching variant found on APKMirror")

            print(f"➡️ VARIANT: {variant_url}")
            await page.goto(variant_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1.0, 2.0))
            await page.wait_for_selector("a.downloadButton", timeout=45000)

            print("⬇️ Resolving download URL...")
            btn_href = await page.get_attribute("a.downloadButton", "href")
            if not btn_href:
                raise Exception("Download button has no href")
            if not btn_href.startswith("http"):
                btn_href = "https://www.apkmirror.com" + btn_href

            await page.goto(btn_href, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2.0, 3.5))
            await page.wait_for_selector("a#download-link", timeout=30000)

            print("⬇️ Clicking final download link...")
            out_dir = Path(__file__).parent.parent / "downloads"
            out_dir.mkdir(parents=True, exist_ok=True)

            async with page.expect_download(timeout=120000) as dl_info:
                await page.click("a#download-link")
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
        browser = await p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            viewport={"width": 1366, "height": 768}
        )
        page = await context.new_page()
        await setup_stealth(page)

        try:
            listing_url = f"https://www.apkmirror.com/apk/{app_config['org']}/{app_config['slug']}/"
            print(f"🌐 LISTING: {listing_url}")
            await page.goto(listing_url, wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(1.5, 2.5))

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
