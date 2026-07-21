import re
from pathlib import Path

import httpx
import nodriver as uc

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

# NOT: nodriver aktif geliştirilen, hızlı değişen bir kütüphane. Aşağıdaki
# select/select_all/attrs/text API'leri deneme sırasında (test edilmeden)
# yazıldı - versiyona göre küçük farklar çıkarsa ilk çalıştırmada log'a
# bakıp birlikte düzeltiriz.


async def _start_browser():
    return await uc.start(
        headless=True,
        browser_args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            f"--user-agent={USER_AGENT}",
        ],
    )


async def _page_exists(tab, url: str) -> bool:
    try:
        await tab.get(url)
        await tab.sleep(0.6)
        row = await tab.select(".table-row", timeout=3)
        return row is not None
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
    await tab.sleep(1)

    links = await tab.select_all("a[href*='-release/']")
    slug_part = f"-{version_slug}-"

    for link in links or []:
        href = link.attrs.get("href", "") if hasattr(link, "attrs") else ""
        if slug_part in href:
            return href if href.startswith("http") else "https://www.apkmirror.com" + href

    raise RuntimeError(f"No APKMirror release page found for version {version}")


def _has_dpi_pattern(text: str) -> bool:
    return bool(re.search(r"\d+-640dpi", text))


async def _extract_variant_url(tab, force_build: str | None, app_name: str) -> str | None:
    rows = await tab.select_all(".table-row")

    standalone_nodpi = None
    standalone_anydpi = None
    bundle_nodpi = None
    bundle_anydpi = None

    allowed_archs = [
        "universal", "evrensel", "noarch",
        "arm64-v8a", "arm64-v8a + armeabi-v7a", "arm64-v8a + armeabi",
    ]

    for row in rows or []:
        cells = await row.query_selector_all(".table-cell")
        if len(cells) < 4:
            continue

        link = await cells[0].query_selector("a.accent_color")
        if not link:
            continue

        cell0_text = (cells[0].text or "").strip()
        if force_build and force_build not in cell0_text:
            continue

        badge = await cells[0].query_selector(".apkm-badge")
        badge_text = (badge.text or "").upper() if badge else ""
        is_bundle = "BUNDLE" in badge_text or "PAKET" in badge_text

        if app_name == "instagram" and not is_bundle:
            continue

        arch_text = (cells[1].text or "").strip().lower()
        dpi_text = (cells[3].text or "").strip().lower()

        is_target_arch = arch_text == "" or any(a in arch_text for a in allowed_archs)
        is_target_dpi = (
            dpi_text == ""
            or "nodpi" in dpi_text
            or "anydpi" in dpi_text
            or _has_dpi_pattern(dpi_text)
        )

        if is_target_arch and is_target_dpi:
            href = link.attrs.get("href")
            if not is_bundle:
                if "nodpi" in dpi_text:
                    standalone_nodpi = href
                else:
                    standalone_anydpi = href
            else:
                if "nodpi" in dpi_text:
                    bundle_nodpi = href
                else:
                    bundle_anydpi = href

    return standalone_nodpi or standalone_anydpi or bundle_nodpi or bundle_anydpi


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
        await tab.select(".table-row", timeout=10)

        variant_url = await _extract_variant_url(tab, force_build, app_name)
        if not variant_url:
            raise RuntimeError("No matching variant found on APKMirror")

        if variant_url.startswith("/"):
            variant_url = "https://www.apkmirror.com" + variant_url

        print("➡️ VARIANT:", variant_url)

        await tab.get(variant_url)
        download_btn = await tab.select("a.downloadButton", timeout=10)
        if not download_btn:
            raise RuntimeError("Download button not found")

        confirm_href = download_btn.attrs.get("href")
        if not confirm_href:
            raise RuntimeError("Download button has no href")
        if confirm_href.startswith("/"):
            confirm_href = "https://www.apkmirror.com" + confirm_href

        print("⬇️ Confirm page:", confirm_href)
        await tab.get(confirm_href)

        final_link_el = await tab.select("#download-link", timeout=10)
        if not final_link_el:
            raise RuntimeError("Final download link not found")

        final_url = final_link_el.attrs.get("href")
        if not final_url:
            raise RuntimeError("Final download link has no href")
        if final_url.startswith("/"):
            final_url = "https://www.apkmirror.com" + final_url

        print("🔗 Final URL:", final_url)

        out_dir = Path(__file__).resolve().parent.parent / "downloads"
        out_dir.mkdir(parents=True, exist_ok=True)

        cookie_dict = {}
        try:
            cookies = await browser.cookies.get_all()
            cookie_dict = {c.name: c.value for c in (cookies or [])}
        except Exception:
            pass  # cookie taşımak başarısız olsa da APKMirror'ın nihai dosya linki genelde herkese açık

        file_name = final_url.split("/")[-1].split("?")[0] or f"{app_name}.apk"
        if not file_name.endswith(".apk"):
            file_name = f"{app_name}-{version}.apk"

        file_path = out_dir / file_name

        async with httpx.AsyncClient(follow_redirects=True, timeout=None, cookies=cookie_dict) as client:
            async with client.stream("GET", final_url, headers={"User-Agent": USER_AGENT}) as res:
                if res.status_code >= 400:
                    raise RuntimeError(f"Download HTTP {res.status_code}")
                with open(file_path, "wb") as f:
                    async for chunk in res.aiter_bytes():
                        f.write(chunk)

        print("📦 DONE:", file_path)
        return str(file_path)

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

        await tab.get(listing_url)
        link = await tab.select("a[href*='-release/']", timeout=10)
        if not link:
            return None

        href = link.attrs.get("href")
        text = link.text or ""

        match = re.search(r"\d+(?:\.\d+)+", text)

        return {"version": match.group(0) if match else None, "href": href}

    finally:
        browser.stop()
