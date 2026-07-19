#!/usr/bin/env python3
"""
Morpe APK Patcher – full Python rewrite
– stealth browser for APKMirror
– resumable GitHub downloads
– automatic release upload
"""

import asyncio
import os
import re
import random
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import httpx
from playwright.async_api import async_playwright
from playwright_stealth import stealth

# --------------- environment ---------------
GITHUB_TOKEN = os.environ["GITHUB_TOKEN"]
GITHUB_REPOSITORY = os.environ["GITHUB_REPOSITORY"]
TARGET_APP = os.environ.get("TARGET_APP", "all")

DISPLAY_NAMES = {
    "youtube": "YouTube",
    "youtube-music": "YT.Music",
    "reddit": "Reddit",
    "twitter": "Twitter",
    "instagram": "Instagram",
    "github": "GitHub",
    "niagara-launcher": "Niagara Launcher",
    "pydroid3": "PyDroid3",
    "smart-launcher": "Smart Launcher",
    "wps-office": "WPS Office",
    "gboard": "Gboard",
    "speedtest": "Speedtest",
    "solid-explorer": "Solid Explorer",
    "brave": "Brave",
}

APPS_CONFIG = {
    "youtube": {
        "pkg": "com.google.android.youtube",
        "patch_source": "morphe",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/youtube/FF0000",
        "exclude": [],
        "enable": [],
        "source": "apkmirror",
        "apkmirror_org": "google-inc",
        "apkmirror_slug": "youtube",
    },
    "youtube-music": {
        "pkg": "com.google.android.apps.youtube.music",
        "patch_source": "morphe",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/youtubemusic/FF0000",
        "exclude": [],
        "enable": [],
        "source": "apkmirror",
        "apkmirror_org": "google-inc",
        "apkmirror_slug": "youtube-music",
    },
    "reddit": {
        "pkg": "com.reddit.frontpage",
        "patch_source": "morphe",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/reddit/FF4500",
        "exclude": [],
        "enable": [],
        "source": "apkmirror",
        "apkmirror_org": "reddit-inc",
        "apkmirror_slug": "reddit",
    },
    "twitter": {
        "pkg": "com.twitter.android",
        "patch_source": "piko",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/x/000000",
        "exclude": ["Dynamic color"],
        "enable": ["Bring back twitter", "Disunify xchat system", "Export all activities"],
        "source": "apkmirror",
        "apkmirror_org": "x-corp",
        "apkmirror_slug": "twitter",
        "apkmirror_release_slug": "x",
    },
    "instagram": {
        "pkg": "com.instagram.android",
        "patch_source": "piko",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/instagram/E4405F",
        "exclude": [],
        "enable": [],
        "force_version": "435.0.0.37.76",
        "force_build": "384109456",
        "source": "apkmirror",
        "apkmirror_org": "instagram",
        "apkmirror_slug": "instagram-instagram",
    },
    "github": {
        "pkg": "com.github.android",
        "patch_source": "hoodles",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/github/ffffff",
        "exclude": [],
        "enable": [],
        "source": "apkmirror",
        "apkmirror_org": "github",
        "apkmirror_slug": "github-2",
    },
    "niagara-launcher": {
        "pkg": "bitpit.launcher",
        "patch_source": "hoodles",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=niagaralauncher.app",
        "exclude": [],
        "enable": [],
        "force_version": "1.16.8",
        "source": "apkmirror",
        "apkmirror_org": "mellowdrop-studio",
        "apkmirror_slug": "niagara-launcher-🔹-fresh-clean",
    },
    "pydroid3": {
        "pkg": "ru.iiec.pydroid3",
        "patch_source": "hoodles",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=pydroid3.com",
        "exclude": [],
        "enable": [],
        "source": "apkmirror",
        "apkmirror_org": "lider-soft-kz",
        "apkmirror_slug": "pydroid-3-ide-for-python-3",
    },
    "smart-launcher": {
        "pkg": "ginlemon.flowerfree",
        "patch_source": "hoodles",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=smartlauncher.net",
        "exclude": [],
        "enable": [],
        "source": "apkmirror",
        "apkmirror_org": "smart-launcher-team",
        "apkmirror_slug": "smart-launcher",
    },
    "wps-office": {
        "pkg": "cn.wps.moffice_eng",
        "patch_source": "hoodles",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=wps.com",
        "exclude": [],
        "enable": [],
        "source": "github",
        "github_tag": "WPSOffice",
    },
    "gboard": {
        "pkg": "com.google.android.inputmethod.latin",
        "patch_source": "adobo",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/google/4285F4",
        "exclude": [],
        "enable": [
            "Enable voice typing in incognito",
            "Enable key shape selection",
            "Enable clipboard in incognito",
            "Enable access points menu redesign",
            "Enable Undo feature",
            "Enable OCR feature",
            "Always-incognito mode",
        ],
        "source": "github",
        "github_tag": "Gboard",
    },
    "speedtest": {
        "pkg": "org.zwanoo.android.speedtest",
        "patch_source": "rushi",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=speedtest.net",
        "exclude": [],
        "enable": [],
        "force_version": "7.0.7",
        "source": "github",
        "github_tag": "Speedtest",
    },
    "solid-explorer": {
        "pkg": "pl.solidexplorer2",
        "patch_source": "rushi",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=solidexplorer.com",
        "exclude": [],
        "enable": [],
        "source": "github",
        "github_tag": "SolidExplorer",
    },
    "brave": {
        "pkg": "com.brave.browser",
        "patch_source": "bufferk",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/brave/FB542B",
        "exclude": [],
        "enable": [],
        "source": "apkmirror",
        "apkmirror_org": "brave-software",
        "apkmirror_slug": "brave-browser",
    },
}

PATCH_SOURCES = {
    "morphe": {"owner": "MorpheApp", "repo": "morphe-patches", "prerelease": True},
    "piko": {"owner": "crimera", "repo": "piko", "prerelease": True},
    "hoodles": {"owner": "hoo-dles", "repo": "morphe-patches", "prerelease": True},
    "adobo": {"owner": "jkennethcarino", "repo": "adobo", "prerelease": True},
    "rushi": {"owner": "rushiranpise", "repo": "morphe-patches", "prerelease": True},
    "bufferk": {"owner": "bufferk", "repo": "morphe-patches", "prerelease": True},
}

PROCESS_ORDER = [
    "youtube", "youtube-music", "reddit", "twitter", "instagram",
    "github", "niagara-launcher", "pydroid3", "smart-launcher",
    "wps-office", "gboard", "speedtest", "solid-explorer", "brave",
]

API_HEADERS = {
    "User-Agent": "morphe-patcher/1.0",
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

# Extended stealth arguments for Chromium
STEALTH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-infobars",
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-web-security",
    "--disable-features=IsolateOrigins,site-per-process",
    "--disable-site-isolation-trials",
    "--disable-component-update",
    "--disable-default-apps",
    "--disable-domain-reliability",
    "--disable-hang-monitor",
    "--disable-ipc-flooding-protection",
    "--disable-popup-blocking",
    "--disable-prompt-on-repost",
    "--disable-renderer-backgrounding",
    "--disable-sync",
    "--force-color-profile=srgb",
    "--metrics-recording-only",
    "--no-first-run",
    "--password-store=basic",
    "--use-mock-keychain",
    "--export-tagged-pdf",
    "--enable-features=NetworkService,NetworkServiceInProcess",
]


# --------------- helper functions ---------------
def extract_versions(output: str):
    results = []
    in_section = False
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("Most common compatible versions"):
            in_section = True
            continue
        if in_section and not line:
            break
        if in_section:
            m = re.match(r"^(\d+\.\d+\.\d+(?:-[a-zA-Z]+\.\d+)?)\s+\((\d+)\s+patches\)", line)
            if m:
                results.append({"version": m.group(1), "patches": int(m.group(2))})
    if not results:
        versions = re.findall(r"\d+\.\d+\.\d+(?:-[a-zA-Z]+\.\d+)?", output)
        return [{"version": v, "patches": 0} for v in versions]
    return results


def version_core(v: str):
    return v.split("-")[0]


def pick_latest_version(versions):
    if not versions:
        return None
    sorted_versions = sorted(
        versions,
        key=lambda x: (x["patches"], [int(p) for p in version_core(x["version"]).split(".")]),
        reverse=True,
    )
    return sorted_versions[0]["version"]


def to_apkmirror_version(version: str):
    return version.replace(".", "-")


async def human_delay(page, min_ms=500, max_ms=2000):
    await page.wait_for_timeout(random.randint(min_ms, max_ms))


async def random_scroll(page):
    await page.evaluate("window.scrollBy(0, {})".format(random.randint(100, 400)))


async def random_mouse_move(page):
    await page.mouse.move(random.randint(100, 800), random.randint(100, 600))


# --------------- GitHub asset download ---------------
async def download_github_asset(owner, repo, match_fn, prerelease=False):
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        if prerelease:
            url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        else:
            url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

        resp = await client.get(url, headers=API_HEADERS)
        resp.raise_for_status()
        data = resp.json()

        if prerelease:
            if not isinstance(data, list) or not data:
                raise Exception("No releases found")
            release = data[0]
        else:
            release = data

        assets = release.get("assets", [])
        asset = next((a for a in assets if match_fn(a["name"])), None)
        if not asset:
            raise Exception("Asset not found")

        name = asset["name"]
        if not Path(name).exists() or Path(name).stat().st_size < 1024:
            download_url = asset["browser_download_url"]
            headers = {
                "User-Agent": API_HEADERS["User-Agent"],
                "Accept": "*/*",
                "Authorization": f"Bearer {GITHUB_TOKEN}",
            }
            async with client.stream("GET", download_url, headers=headers) as r:
                r.raise_for_status()
                with open(name, "wb") as f:
                    async for chunk in r.aiter_bytes(chunk_size=8192):
                        f.write(chunk)

        return {"name": name, "body": release.get("body", ""), "tag": release.get("tag_name", "")}


# --------------- APKMirror stealth browser ---------------
async def new_stealth_browser(playwright, accept_downloads=False):
    browser = await playwright.chromium.launch(
        headless=True,
        args=STEALTH_ARGS,
    )
    context = await browser.new_context(
        accept_downloads=accept_downloads,
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
        timezone_id="America/New_York",
        permissions=[],  # no extra permissions
        geolocation={"longitude": -73.97, "latitude": 40.75},  # New York
        color_scheme="light",
        extra_http_headers={
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    page = await context.new_page()
    # Apply full stealth patches
    await stealth(page)
    # Override some navigator properties to avoid detection
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = { runtime: {} };
    """)
    return browser, context, page


async def get_latest_apkmirror_version(org, slug):
    async with async_playwright() as p:
        browser, context, page = await new_stealth_browser(p, accept_downloads=False)
        try:
            listing_url = f"https://www.apkmirror.com/apk/{org}/{slug}/"
            await page.goto(listing_url, wait_until="domcontentloaded", timeout=60000)
            await human_delay(page, 3000, 6000)
            await random_scroll(page)
            await random_mouse_move(page)
            await human_delay(page, 1000, 2000)

            result = await page.evaluate("""() => {
                const link = document.querySelector('a[href*="-release/"]');
                if (!link) return null;
                const row = link.closest('div, li, tr') || link.parentElement;
                const text = row ? row.innerText : link.innerText;
                const match = text.match(/\\d+(?:\\.\\d+)+/);
                return { version: match ? match[0] : null, href: link.href };
            }""")
            return result
        finally:
            await browser.close()


async def download_from_apkmirror(version, app_key, force_build=None):
    config = APPS_CONFIG[app_key]
    org = config["apkmirror_org"]
    slug = config["apkmirror_slug"]
    release_slug = config.get("apkmirror_release_slug", slug)

    async with async_playwright() as p:
        browser, context, page = await new_stealth_browser(p, accept_downloads=True)

        try:
            version_slug = to_apkmirror_version(version)
            folder_url = f"https://www.apkmirror.com/apk/{org}/{slug}"
            candidates = [
                f"{folder_url}/{release_slug}-{version_slug}-release/",
                f"{folder_url}/{release_slug}-{version_slug}-release-0-release/",
                f"{folder_url}/{release_slug}-{version_slug}-beta-0-release/",
                f"{folder_url}/{release_slug}-{version_slug}-beta-1-release/",
            ]

            list_url = None
            for candidate in candidates:
                try:
                    resp = await page.goto(candidate, wait_until="domcontentloaded", timeout=60000)
                    if resp and resp.status != 404:
                        has_rows = await page.query_selector(".table-row")
                        if has_rows:
                            list_url = candidate
                            break
                except Exception:
                    pass
                await human_delay(page, 2000, 4000)

            if not list_url:
                listing = f"{folder_url}/"
                await page.goto(listing, wait_until="domcontentloaded", timeout=60000)
                await human_delay(page, 4000, 8000)
                await random_scroll(page)
                await random_mouse_move(page)
                found = await page.evaluate("""([versionSlug]) => {
                    const links = Array.from(document.querySelectorAll('a[href*="-release/"]'));
                    const match = links.find(a => a.href.includes(versionSlug));
                    return match ? match.href : null;
                }""", [f"-{version_slug}-"])
                if not found:
                    raise Exception(f"No APKMirror release page for version {version}")
                list_url = found

            await page.goto(list_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector(".table-row", timeout=60000)
            await human_delay(page, 3000, 5000)
            await random_scroll(page)

            variant_url = await page.evaluate(
                f"""(forceBuild) => {{
                    const rows = document.querySelectorAll('.table-row');
                    const allowedArchs = ['universal', 'evrensel', 'noarch', 'arm64-v8a', 'arm64-v8a + armeabi-v7a', 'arm64-v8a + armeabi'];
                    let best = null;
                    for (const row of rows) {{
                        const cells = row.querySelectorAll('.table-cell');
                        if (cells.length < 4) continue;
                        const link = cells[0].querySelector('a.accent_color');
                        if (!link) continue;
                        if (forceBuild && !cells[0].innerText.includes(forceBuild)) continue;
                        const badge = cells[0].querySelector('.apkm-badge');
                        const isBundle = badge && (badge.innerText.toUpperCase().includes('BUNDLE') || badge.innerText.toUpperCase().includes('PAKET'));
                        if ('{app_key}' === 'instagram' && !isBundle) continue;
                        const archText = cells[1].innerText.trim().toLowerCase();
                        const dpiText = cells[3].innerText.trim().toLowerCase();
                        const isArchOk = archText === '' || allowedArchs.some(a => archText.includes(a));
                        const isDpiOk = dpiText === '' || dpiText.includes('nodpi') || dpiText.includes('anydpi') || /\\d+-640dpi/.test(dpiText);
                        if (isArchOk && isDpiOk) {{
                            const isNodpi = dpiText.includes('nodpi');
                            if (!best || (isNodpi && !best.nodpi)) {{
                                best = {{ href: link.href, nodpi: isNodpi, bundle: isBundle }};
                            }}
                        }}
                    }}
                    return best ? best.href : null;
                }}""",
                force_build,
            )

            if not variant_url:
                raise Exception("No matching variant found on APKMirror")

            await page.goto(variant_url, wait_until="domcontentloaded", timeout=60000)
            # Wait for download button or fallback link
            try:
                await page.wait_for_selector("a.downloadButton, #download-link", timeout=60000)
            except Exception:
                # extra wait and human actions
                await human_delay(page, 5000, 10000)
                await random_scroll(page)
                await random_mouse_move(page)
                await page.wait_for_selector("a.downloadButton, #download-link", timeout=30000)

            await human_delay(page, 2000, 4000)

            # Extract final download URL (prefer direct link)
            download_url = await page.evaluate("""() => {
                const btn = document.querySelector('a.downloadButton');
                if (btn && btn.href) return btn.href;
                const fallback = document.querySelector('#download-link');
                return fallback ? fallback.href : null;
            }""")

            if not download_url:
                raise Exception("Download URL not found on APKMirror")

            out_dir = Path.cwd() / "downloads"
            out_dir.mkdir(exist_ok=True)

            # Use httpx with full headers to mimic browser
            async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
                headers = {
                    "User-Agent": random.choice(USER_AGENTS),
                    "Accept": "*/*",
                    "Referer": variant_url,
                    "Accept-Language": "en-US,en;q=0.9",
                    "Connection": "keep-alive",
                }
                async with client.stream("GET", download_url, headers=headers) as r:
                    r.raise_for_status()
                    content_disposition = r.headers.get("content-disposition", "")
                    filename_match = re.search(r'filename[^;=\n]*=((["\']).*?\2|[^;\n]*)', content_disposition)
                    if filename_match:
                        filename = filename_match.group(1).strip('"\'')
                    else:
                        filename = download_url.split("/")[-1].split("?")[0] or f"{app_key}.apk"

                    filepath = out_dir / filename
                    with open(filepath, "wb") as f:
                        async for chunk in r.aiter_bytes(8192):
                            f.write(chunk)

            return str(filepath)

        finally:
            await browser.close()


# --------------- GitHub download (fuckpdf/Depo) ---------------
async def download_from_github(app_key):
    config = APPS_CONFIG[app_key]
    tag = config["github_tag"]
    async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
        api_url = f"https://api.github.com/repos/fuckpdf/Depo/releases/tags/{tag}"
        resp = await client.get(api_url, headers={"User-Agent": "morphe-patcher"})
        resp.raise_for_status()
        release = resp.json()
        assets = release.get("assets", [])
        asset = next((a for a in assets if a["name"].endswith(".apk") or a["name"].endswith(".apkm")), None)
        if not asset:
            raise Exception(f"No APK asset found in GitHub release for {app_key}")
        out_dir = Path.cwd() / "downloads"
        out_dir.mkdir(exist_ok=True)
        filepath = out_dir / asset["name"]
        download_url = asset["browser_download_url"]
        headers = {
            "User-Agent": "morphe-patcher",
            "Accept": "*/*",
            "Authorization": f"Bearer {GITHUB_TOKEN}",
        }
        async with client.stream("GET", download_url, headers=headers) as r:
            r.raise_for_status()
            with open(filepath, "wb") as f:
                async for chunk in r.aiter_bytes(8192):
                    f.write(chunk)
        return str(filepath)


# --------------- patching ---------------
def patch_apk(desktop, patches, apk_path, extra_args="", arch="arm64-v8a"):
    ks_path = os.environ.get("KS_PATH")
    ks_password = os.environ.get("KS_PASSWORD")
    ks_alias = os.environ.get("KS_ALIAS")
    key_password = os.environ.get("KEY_PASSWORD")

    cmd = ["java", "-jar", desktop, "patch", "--patches", patches]
    if arch:
        cmd.extend(["--striplibs", arch])
    if ks_path and Path(ks_path).exists() and ks_password and ks_alias and key_password:
        cmd.extend([
            "--keystore", ks_path,
            "--keystore-password", ks_password,
            "--keystore-entry-alias", ks_alias,
            "--keystore-entry-password", key_password,
        ])
    if extra_args.strip():
        cmd.extend(extra_args.strip().split())
    cmd.append(apk_path)

    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout + result.stderr

    if "Applying 0 patches" in output:
        raise Exception("Applying 0 patches – incompatible version")

    match = re.search(r"INFO:\s+Saved to\s+([^\r\n]+\.apk)", output, re.IGNORECASE)
    if not match:
        raise Exception(f"Cannot find patched APK path in output:\n{output}")
    patched = match.group(1).strip()
    if not Path(patched).exists():
        raise Exception(f"Patched APK does not exist: {patched}")
    return patched


# --------------- release helpers ---------------
async def create_release(tag, name, body):
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases"
        resp = await client.post(url, headers=API_HEADERS, json={
            "tag_name": tag,
            "name": name,
            "body": body,
            "draft": False,
            "prerelease": False,
            "make_latest": "true",
        })
        resp.raise_for_status()
        return resp.json()


async def upload_asset(release, filepath):
    async with httpx.AsyncClient(timeout=120) as client:
        filename = Path(filepath).name
        upload_url = release["upload_url"].replace("{?name,label}", f"?name={filename}")
        with open(filepath, "rb") as f:
            data = f.read()
        headers = {
            **API_HEADERS,
            "Content-Type": "application/vnd.android.package-archive",
            "Content-Length": str(len(data)),
        }
        resp = await client.post(upload_url, headers=headers, content=data)
        resp.raise_for_status()
        return resp.json()


async def get_assets(release_id):
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/{release_id}/assets"
        resp = await client.get(url, headers=API_HEADERS)
        resp.raise_for_status()
        return resp.json()


async def delete_asset(asset_id):
    async with httpx.AsyncClient(timeout=30) as client:
        url = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/assets/{asset_id}"
        resp = await client.delete(url, headers=API_HEADERS)
        resp.raise_for_status()


async def upload_with_replace(release, filepath):
    filename = Path(filepath).name
    assets = await get_assets(release["id"])
    existing = next((a for a in assets if a["name"] == filename), None)
    if existing:
        await delete_asset(existing["id"])
    await upload_asset(release, filepath)


async def upload_microg(release):
    microg = await download_github_asset("MorpheApp", "MicroG-RE", lambda n: n.endswith(".apk"))
    original = Path.cwd() / microg["name"]
    target = Path.cwd() / "MicroG.apk"
    if original != target and original.exists():
        shutil.move(str(original), str(target))
    assets = await get_assets(release["id"])
    if any(a["name"] == "MicroG.apk" for a in assets):
        return
    await upload_with_replace(release, str(target))


# --------------- per-app processing ---------------
async def process_app(app_key, desktop, patches):
    config = APPS_CONFIG[app_key]
    selected_version = config.get("force_version")
    force_build = config.get("force_build")

    if not selected_version:
        try:
            result = subprocess.run(
                ["java", "-jar", desktop, "list-versions", "-f", config["pkg"],
                 f"--patches={patches}", "--include-experimental"],
                capture_output=True, text=True, timeout=90
            )
            versions = extract_versions(result.stdout)
            if versions:
                selected_version = pick_latest_version(versions)
        except Exception:
            pass

    if config["source"] == "apkmirror":
        if not selected_version:
            latest = await get_latest_apkmirror_version(config["apkmirror_org"], config["apkmirror_slug"])
            if latest:
                selected_version = latest["version"]
        if not selected_version:
            raise Exception(f"Could not determine version for {app_key}")
        apk_path = await download_from_apkmirror(selected_version, app_key, force_build)
    else:
        if not selected_version:
            selected_version = "latest"
        apk_path = await download_from_github(app_key)

    extra_args = []
    for exc in config.get("exclude", []):
        extra_args.append(f'--disable "{exc}"')
    for en in config.get("enable", []):
        extra_args.append(f'--enable "{en}"')
    extra = " ".join(extra_args)

    patched = patch_apk(desktop, patches, apk_path, extra, config["arch"])

    display = DISPLAY_NAMES.get(app_key, app_key)
    final_name = f"{display}-{selected_version}.apk"
    final_path = Path.cwd() / final_name
    shutil.copy2(patched, final_path)

    return {
        "app_name": app_key,
        "display_name": display,
        "icon": config["icon"],
        "patch_source": config["patch_source"],
        "name": final_name,
        "path": str(final_path),
        "version": selected_version,
    }


# --------------- main ---------------
async def main():
    desktop_asset = await download_github_asset(
        "MorpheApp", "morphe-desktop",
        lambda n: "desktop" in n and n.endswith(".jar")
    )
    desktop = desktop_asset["name"]

    apps_to_process = PROCESS_ORDER if TARGET_APP == "all" else [TARGET_APP]
    needed_sources = set(APPS_CONFIG[k]["patch_source"] for k in apps_to_process)

    patch_assets = {}
    notes = {}
    for source_key in needed_sources:
        cfg = PATCH_SOURCES[source_key]
        asset = await download_github_asset(
            cfg["owner"], cfg["repo"],
            lambda n: n.endswith(".mpp"),
            cfg["prerelease"]
        )
        patch_assets[source_key] = asset["name"]
        notes[source_key] = (
            f"\n<details>\n<summary>{cfg['owner']} Release Notes "
            f"({asset['tag']})</summary>\n<br>\n\n{asset['body']}\n\n</details>\n"
        )

    patched_list = []
    for app_key in apps_to_process:
        try:
            result = await process_app(
                app_key, desktop,
                patch_assets[APPS_CONFIG[app_key]["patch_source"]]
            )
            patched_list.append(result)
        except Exception as e:
            print(f"❌ {app_key} failed: {e}")

    if not patched_list:
        print("No apps patched, exiting.")
        return

    now = datetime.now(timezone.utc)
    tag = now.strftime("build-%Y-%m-%dT%H-%M-%SZ")
    name = now.strftime("Patched APKs · %B %d, %Y")
    body = "### 📦 Latest Patched APKs\n\n"
    for apk in patched_list:
        body += f'* <img src="{apk["icon"]}" width="16" height="16"> **{apk["display_name"]}**\n'
    body += "\n---\n\n"
    for source_key in sorted(needed_sources):
        if source_key in notes:
            body += notes[source_key]

    release = await create_release(tag, name, body)

    microg_uploaded = False
    for apk in patched_list:
        await upload_with_replace(release, apk["path"])
        if not microg_uploaded and apk["app_name"] in ("youtube", "youtube-music"):
            await upload_microg(release)
            microg_uploaded = True

    print("✅ All done – release published.")


if __name__ == "__main__":
    asyncio.run(main())
