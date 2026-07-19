import asyncio
import os
import re
from pathlib import Path
from playwright.async_api import async_playwright
import logging

logger = logging.getLogger(__name__)

APP_SITES = {
    "youtube": {"org": "google-inc", "slug": "youtube"},
    "youtube-music": {"org": "google-inc", "slug": "youtube-music"},
    "reddit": {"org": "reddit-inc", "slug": "reddit"},
    "twitter": {"org": "x-corp", "slug": "twitter", "release_slug": "x"},
    "instagram": {"org": "instagram", "slug": "instagram-instagram"},
    "github": {"org": "github", "slug": "github-2"},
    "niagara-launcher": {"org": "mellowdrop-studio", "slug": "niagara-launcher-🔹-fresh-clean"},
    "pydroid3": {"org": "lider-soft-kz", "slug": "pydroid-3-ide-for-python-3"},
    "smart-launcher": {"org": "smart-launcher-team", "slug": "smart-launcher"},
    "wps-office": {"org": "wps-software-pte-ltd", "slug": "wps-office-pdf"},
    "gboard": {"org": "google-inc", "slug": "gboard"},
    "speedtest": {"org": "ookla", "slug": "speedtest"},
    "solid-explorer": {"org": "neatbytes", "slug": "solid-explorer-file-manager"},
    "brave": {"org": "brave-software", "slug": "brave-browser"},
}

def to_apk_mirror_version(version):
    return version.replace(".", "-")

async def page_exists(page, url):
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=10000)
        if response.status == 404:
            return False
        rows = await page.query_selector_all(".table-row")
        return len(rows) > 0
    except Exception:
        return False

async def resolve_list_url(page, app_config, version):
    version_slug = to_apk_mirror_version(version)
    name_part = app_config.get("release_slug") or app_config["slug"]
    folder_url = f"https://www.apkmirror.com/apk/{app_config['org']}/{app_config['slug']}"

    candidates = [
        f"{folder_url}/{name_part}-{version_slug}-release/",
        f"{folder_url}/{name_part}-{version_slug}-release-0-release/",
        f"{folder_url}/{name_part}-{version_slug}-beta-0-release/",
        f"{folder_url}/{name_part}-{version_slug}-beta-1-release/"
    ]

    for candidate in candidates:
        logger.info(f"🔎 TRY: {candidate}")
        if await page_exists(page, candidate):
            return candidate

    logger.info("⚠️ No direct match, scanning app listing page...")
    listing_url = f"{folder_url}/"
    await page.goto(listing_url, wait_until="domcontentloaded")

    elements = await page.query_selector_all("a[href*='-release/']")
    for elem in elements:
        href = await elem.get_attribute("href")
        if href and f"-{version_slug}-" in href:
            return f"https://www.apkmirror.com{href}"

    raise Exception(f"No APKMirror release page found for version {version}")

async def download_apk(version, app_name="youtube", force_build=None):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            accept_downloads=True,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            app_config = APP_SITES.get(app_name)
            if not app_config:
                raise Exception(f"Unknown appName '{app_name}'")

            list_url = await resolve_list_url(page, app_config, version)
            logger.info(f"🌐 LIST: {list_url}")

            await page.goto(list_url, wait_until="domcontentloaded")
            await page.wait_for_selector(".table-row", timeout=15000)

            variant_url = None
            rows = await page.query_selector_all(".table-row")
            for row in rows:
                cells = await row.query_selector_all(".table-cell")
                if len(cells) < 4:
                    continue
                link = await cells[0].query_selector("a.accent_color")
                if not link:
                    continue
                href = await link.get_attribute("href")
                if not href:
                    continue

                if force_build:
                    cell_text = await cells[0].inner_text()
                    if force_build not in cell_text:
                        continue

                badge = await cells[0].query_selector(".apkm-badge")
                is_bundle = False
                if badge:
                    badge_text = (await badge.inner_text()).upper()
                    if "BUNDLE" in badge_text or "PAKET" in badge_text:
                        is_bundle = True

                if app_name == "instagram" and not is_bundle:
                    continue

                arch_text = (await cells[1].inner_text()).strip().lower()
                dpi_text = (await cells[3].inner_text()).strip().lower()

                allowed_archs = ["universal", "evrensel", "noarch", "arm64-v8a", "arm64-v8a + armeabi-v7a", "arm64-v8a + armeabi"]
                is_target_arch = arch_text == "" or any(arch in arch_text for arch in allowed_archs)

                is_target_dpi = (
                    dpi_text == "" or
                    "nodpi" in dpi_text or
                    "anydpi" in dpi_text or
                    bool(re.search(r'\d+-640dpi', dpi_text))
                )

                if is_target_arch and is_target_dpi:
                    if not is_bundle and "nodpi" in dpi_text:
                        variant_url = href
                        break
                    elif not is_bundle and variant_url is None:
                        variant_url = href
                    elif is_bundle and "nodpi" in dpi_text and variant_url is None:
                        variant_url = href
                    elif is_bundle and variant_url is None:
                        variant_url = href

            if not variant_url:
                raise Exception("No matching variant found on APKMirror")

            if not variant_url.startswith("http"):
                variant_url = f"https://www.apkmirror.com{variant_url}"
            logger.info(f"➡️ VARIANT: {variant_url}")

            await page.goto(variant_url, wait_until="domcontentloaded")
            await page.wait_for_selector("a.downloadButton", timeout=15000)

            out_dir = Path("downloads")
            out_dir.mkdir(exist_ok=True)

            async with page.expect_download() as download_info:
                await page.click("a.downloadButton")
            download = await download_info.value

            if not download:
                logger.warning("⚠️ Main download failed → fallback link")
                fallback_url = await page.get_attribute("#download-link", "href")
                async with context.new_page() as page2:
                    async with page2.expect_download() as download_info2:
                        await page2.goto(fallback_url, wait_until="domcontentloaded")
                    download = await download_info2.value

            file_name = download.suggested_filename
            file_path = out_dir / file_name
            await download.save_as(str(file_path))
            logger.info(f"📦 DONE: {file_path}")
            return str(file_path)

        except Exception as e:
            logger.error(f"❌ ERROR: {e}")
            raise
        finally:
            await browser.close()

async def get_latest_listing(app_name):
    app_config = APP_SITES.get(app_name)
    if not app_config:
        raise Exception(f"Unknown appName '{app_name}'")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            listing_url = f"https://www.apkmirror.com/apk/{app_config['org']}/{app_config['slug']}/"
            logger.info(f"🌐 LISTING: {listing_url}")
            await page.goto(listing_url, wait_until="domcontentloaded")

            release_links = await page.evaluate('''
                () => {
                    const links = document.querySelectorAll('a[href*="-release/"]');
                    return Array.from(links).map(a => a.href);
                }
            ''')

            if not release_links:
                rows = await page.query_selector_all(".table-row")
                for row in rows:
                    link = await row.query_selector("a[href*='-release/']")
                    if link:
                        href = await link.get_attribute("href")
                        if href:
                            release_links.append(f"https://www.apkmirror.com{href}")

            if not release_links:
                logger.warning(f"No release links found for {app_name}")
                return None

            latest_href = release_links[0]
            version_match = re.search(r'/(\d+(?:\.\d+)+)/', latest_href)
            if version_match:
                version = version_match.group(1)
                return {"version": version, "href": latest_href}
            else:
                return None

        except Exception as e:
            logger.error(f"❌ ERROR in get_latest_listing: {e}")
            raise
        finally:
            await browser.close()
