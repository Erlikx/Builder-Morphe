import os
import sys
import re
import time
import random
import requests
import subprocess
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

# Anlık log için
sys.stdout.reconfigure(line_buffering=True)

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("GITHUB_REPOSITORY", "Erlikx/Builder-Morphe")
OUT_DIR = Path("downloads")
OUT_DIR.mkdir(exist_ok=True)
DATA_DIR = Path("morphe-data")
DATA_DIR.mkdir(exist_ok=True)

DISPLAY_NAMES = {
    "youtube": "YouTube", "youtube-music": "YT.Music", "reddit": "Reddit",
    "twitter": "Twitter", "instagram": "Instagram", "github": "GitHub",
    "niagara-launcher": "Niagara Launcher", "pydroid3": "PyDroid3",
    "smart-launcher": "Smart Launcher", "wps-office": "WPS Office",
    "gboard": "Gboard", "speedtest": "Speedtest",
    "solid-explorer": "Solid Explorer", "brave": "Brave"
}

APPS_CONFIG = {
    "youtube": {"pkg": "com.google.android.youtube", "patchSource": "morphe", "am_url": "https://www.apkmirror.com/apk/google-inc/youtube/"},
    "youtube-music": {"pkg": "com.google.android.apps.youtube.music", "patchSource": "morphe", "am_url": "https://www.apkmirror.com/apk/google-inc/youtube-music/"},
    "reddit": {"pkg": "com.reddit.frontpage", "patchSource": "morphe", "am_url": "https://www.apkmirror.com/apk/reddit-inc/reddit/"},
    "twitter": {"pkg": "com.twitter.android", "patchSource": "piko", "am_url": "https://www.apkmirror.com/apk/x-corp/twitter/", "releaseSlug": "x", "exclude": ["Dynamic color"], "enable": ["Bring back twitter", "Disunify xchat system", "Export all activities"]},
    "instagram": {"pkg": "com.instagram.android", "patchSource": "piko", "am_url": "https://www.apkmirror.com/apk/instagram/instagram-instagram/"},
    "github": {"pkg": "com.github.android", "patchSource": "hoodles", "am_url": "https://www.apkmirror.com/apk/github/github-2/"},
    "niagara-launcher": {"pkg": "bitpit.launcher", "patchSource": "hoodles", "am_url": "https://www.apkmirror.com/apk/mellowdrop-studio/niagara-launcher-%f0%9f%94%b9-fresh-clean/"},
    "pydroid3": {"pkg": "ru.iiec.pydroid3", "patchSource": "hoodles", "am_url": "https://www.apkmirror.com/apk/lider-soft-kz/pydroid-3-ide-for-python-3/"},
    "smart-launcher": {"pkg": "ginlemon.flowerfree", "patchSource": "hoodles", "am_url": "https://www.apkmirror.com/apk/smart-launcher-team/smart-launcher/"},
    "wps-office": {"pkg": "cn.wps.moffice_eng", "patchSource": "hoodles", "am_url": "https://www.apkmirror.com/apk/wps-software-pte-ltd/wps-office-pdf/"},
    "gboard": {"pkg": "com.google.android.inputmethod.latin", "patchSource": "adobo", "am_url": "https://www.apkmirror.com/apk/google-inc/gboard/", "enable": ["Enable voice typing in incognito", "Enable key shape selection", "Enable clipboard in incognito", "Enable access points menu redesign", "Enable Undo feature", "Enable OCR feature", "Always-incognito mode"]},
    "speedtest": {"pkg": "org.zwanoo.android.speedtest", "patchSource": "rushi", "am_url": "https://www.apkmirror.com/apk/ookla/speedtest/"},
    "solid-explorer": {"pkg": "pl.solidexplorer2", "patchSource": "rushi", "am_url": "https://www.apkmirror.com/apk/neatbytes/solid-explorer-file-manager/"},
    "brave": {"pkg": "com.brave.browser", "patchSource": "bufferk", "am_url": "https://www.apkmirror.com/apk/brave-software/brave-browser/"}
}

PROCESS_ORDER = list(APPS_CONFIG.keys())

def sleep_jitter(base=2):
    time.sleep(base + random.uniform(0.5, 2.5))

def get_github_headers():
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers

def download_asset(owner, repo, match_str, prerelease=False):
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    if not prerelease: url += "/latest"
    res = requests.get(url, headers=get_github_headers())
    res.raise_for_status()
    data = res.json()
    release = next((r for r in data if r.get("prerelease") == True), data[0]) if prerelease and isinstance(data, list) else data
    asset = next((a for a in release.get("assets", []) if match_str in a["name"]), None)
    if not asset: raise Exception(f"Asset bulunamadı: {match_str}")
    out_path = Path(asset["name"])
    if not out_path.exists():
        r = requests.get(asset["browser_download_url"], stream=True)
        r.raise_for_status()
        with open(out_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
    return {"path": out_path, "body": release.get("body", ""), "tag": release.get("tag_name", "")}

def get_supported_version(desktop_jar, patches_mpp, pkg_name):
    try:
        cmd = ["java", "-jar", str(desktop_jar), "list-versions", "-f", pkg_name, "--patches", str(patches_mpp), "--include-experimental"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        versions = [m.group(1) for line in res.stdout.splitlines() for m in [re.search(r'(\d+\.\d+\.\d+(\.\d+)?)', line)] if m]
        if versions:
            versions = sorted(list(set(versions)), key=lambda s: [int(u) for u in s.split('.') if u.isdigit()], reverse=True)
            return versions[0]
    except: return None

def download_apk(app_name, config, out_dir, target_version=None):
    base_url = config["am_url"]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        page = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36").new_page()
        stealth_sync(page)
        try:
            release_url = None
            if target_version:
                v_slug = target_version.replace(".", "-")
                name_part = config.get("releaseSlug", base_url.rstrip('/').split('/')[-1])
                for c in [f"{base_url}{name_part}-{v_slug}-{s}/" for s in ["release", "release-0-release", "beta-0-release", "beta-1-release"]]:
                    try:
                        res = page.goto(c, wait_until="domcontentloaded", timeout=15000)
                        if res and res.status != 404 and page.locator(".table-row").count() > 0:
                            release_url = c; break
                    except: continue
            if not release_url:
                page.goto(base_url, wait_until="domcontentloaded", timeout=45000)
                latest = page.locator("a[href*='-release/']").first
                release_url = f"https://www.apkmirror.com{latest.get_attribute('href')}"
                page.goto(release_url, wait_until="domcontentloaded", timeout=45000)
            
            page.wait_for_selector(".table-row", timeout=20000)
            for row in page.locator(".table-row").all():
                if any(x in row.inner_text().lower() for x in ["arm64-v8a", "universal", "noarch"]):
                    page.goto(f"https://www.apkmirror.com{row.locator('a.accent_color').first.get_attribute('href')}", wait_until="domcontentloaded")
                    break
            
            page.wait_for_selector("a.downloadButton", timeout=20000)
            page.goto(f"https://www.apkmirror.com{page.locator('a.downloadButton').get_attribute('href')}", wait_until="domcontentloaded")
            page.wait_for_selector("#download-link", timeout=20000)
            direct_link = page.locator("#download-link").get_attribute("href")
            r = requests.get(direct_link, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
            r.raise_for_status()
            path = out_dir / f"{app_name}.apk"
            with open(path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            return path
        finally: browser.close()

def patch_apk(desktop_jar, patches_mpp, apk_path, app_name):
    config = APPS_CONFIG[app_name]
    cmd = ["java", "-jar", str(desktop_jar), "patch", "--patches", str(patches_mpp), "--striplibs", "arm64-v8a"]
    ks = os.environ.get("KS_PATH")
    if ks and Path(ks).exists():
        cmd.extend(["--keystore", ks, "--keystore-password", os.environ.get("KS_PASSWORD", ""), "--keystore-entry-alias", os.environ.get("KS_ALIAS", ""), "--keystore-entry-password", os.environ.get("KEY_PASSWORD", "")])
    for ex in config.get("exclude", []): cmd.extend(["--disable", ex])
    for en in config.get("enable", []): cmd.extend(["--enable", en])
    cmd.append(str(apk_path))
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        for line in res.stdout.splitlines():
            if "Saved to" in line:
                path_str = line.split("Saved to")[-1].strip().lstrip(":")
                final_path = OUT_DIR / f"{DISPLAY_NAMES[app_name]}-latest.apk"
                Path(path_str).rename(final_path)
                return final_path
    except: return None

def create_release(tag, name, body, assets):
    res = requests.post(f"https://api.github.com/repos/{REPO}/releases", headers=get_github_headers(), json={"tag_name": tag, "name": name, "body": body})
    res.raise_for_status()
    upload_url = res.json()["upload_url"].split("{")[0]
    for asset in assets:
        requests.post(f"{upload_url}?name={asset.name}", headers={**get_github_headers(), "Content-Type": "application/vnd.android.package-archive"}, data=open(asset, "rb")).raise_for_status()

def main():
    desktop = download_asset("MorpheApp", "morphe-desktop", ".jar")["path"]
    patches = {
        "morphe": download_asset("MorpheApp", "morphe-patches", ".mpp", True),
        "piko": download_asset("crimera", "piko", ".mpp", True),
        "hoodles": download_asset("hoo-dles", "morphe-patches", ".mpp", True),
        "adobo": download_asset("jkennethcarino", "adobo", ".mpp", True),
        "rushi": download_asset("rushiranpise", "morphe-patches", ".mpp", True),
        "bufferk": download_asset("bufferk", "morphe-patches", ".mpp", True)
    }
    patched_apks = []
    for app in PROCESS_ORDER:
        config = APPS_CONFIG[app]
        mpp = patches[config["patchSource"]]["path"]
        raw = download_apk(app, config, OUT_DIR, get_supported_version(desktop, mpp, config["pkg"]))
        if raw:
            patched = patch_apk(desktop, mpp, raw, app)
            if patched: patched_apks.append(patched)
    if patched_apks:
        tag = f"build-{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}"
        body = "### Latest Patched APKs\n" + "\n".join([f"* {p.name}" for p in patched_apks])
        patched_apks.append(download_asset("MorpheApp", "MicroG-RE", ".apk")["path"])
        create_release(tag, f"Patched APKs {datetime.now().strftime('%Y-%m-%d')}", body, patched_apks)

if __name__ == "__main__":
    main()
