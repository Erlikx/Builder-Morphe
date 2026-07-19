import os
import re
import time
import random
import requests
import subprocess
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

# --- YAPILANDIRMA ---
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
    "solid-explorer": "Solid Explorer", "brave": "Brave", "microg": "MicroG"
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

# --- YARDIMCI FONKSİYONLAR ---
def sleep_jitter(base=2):
    time.sleep(base + random.uniform(0.5, 2.5))

def get_github_headers():
    headers = {"Accept": "application/vnd.github+json"}
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers

def download_github_asset(owner, repo, match_str, prerelease=False):
    print(f"📦 Fetch release: {owner}/{repo}")
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    if not prerelease:
        url += "/latest"
        
    res = requests.get(url, headers=get_github_headers())
    res.raise_for_status()
    
    data = res.json()
    
    if prerelease and isinstance(data, list):
        # Özellikle "prerelease": true olan en güncel sürümü filtreler
        release = next((r for r in data if r.get("prerelease") == True), data[0])
    else:
        release = data
    
    asset = next((a for a in release.get("assets", []) if match_str in a["name"]), None)
    if not asset:
        raise Exception(f"Asset bulunamadı: {match_str}")
        
    print(f"🎯 Selected: {asset['name']}")
    out_path = Path(asset["name"])
    
    if not out_path.exists():
        r = requests.get(asset["browser_download_url"], stream=True)
        r.raise_for_status()
        with open(out_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
    return {"path": out_path, "body": release.get("body", ""), "tag": release.get("tag_name", "")}

def get_supported_version(desktop_jar, patches_mpp, pkg_name):
    """Morphe CLI üzerinden yamanın desteklediği en yüksek önerilen sürümü bulur."""
    print(f"🔍 {pkg_name} için desteklenen sürümler sorgulanıyor...")
    try:
        cmd = [
            "java", "-jar", str(desktop_jar), "list-versions",
            "-f", pkg_name,
            "--patches", str(patches_mpp),
            "--include-experimental"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        versions = []
        for line in res.stdout.splitlines():
            match = re.search(r'(\d+\.\d+\.\d+(\.\d+)?)', line)
            if match:
                versions.append(match.group(1))
                
        if versions:
            versions = list(set(versions))
            # Örn: 21.28.204 gibi sürümleri en yüksekten düşüğe sıralar
            versions.sort(key=lambda s: [int(u) for u in s.split('.') if u.isdigit()], reverse=True)
            print(f"🎯 Önerilen sürüm bulundu: {versions[0]}")
            return versions[0]
            
    except Exception as e:
        print(f"⚠️ Sürüm sorgulama başarısız: {e}")
        
    return None

# --- APKMIRROR (PLAYWRIGHT) ---
def download_from_apkmirror(app_name, target_version=None):
    config = APPS_CONFIG[app_name]
    base_url = config["am_url"]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
            accept_downloads=True,
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        stealth_sync(page)
        
        try:
            release_url = None
            
            # Eğer belirli bir sürüm istendiyse, doğrudan o varyanta ulaşmayı dener
            if target_version:
                version_slug = target_version.replace(".", "-")
                name_part = config.get("releaseSlug", base_url.rstrip('/').split('/')[-1])
                
                candidates = [
                    f"{base_url}{name_part}-{version_slug}-release/",
                    f"{base_url}{name_part}-{version_slug}-release-0-release/",
                    f"{base_url}{name_part}-{version_slug}-beta-0-release/",
                    f"{base_url}{name_part}-{version_slug}-beta-1-release/"
                ]
                
                for candidate in candidates:
                    print(f"🔎 TRY: {candidate}")
                    try:
                        res = page.goto(candidate, wait_until="domcontentloaded", timeout=15000)
                        if res and res.status != 404 and page.locator(".table-row").count() > 0:
                            release_url = candidate
                            print(f"🎯 Özel sürüm sayfası bulundu: {release_url}")
                            break
                    except Exception:
                        continue
            
            # Spesifik sürüm bulunamazsa veya istenmediyse ana sayfadan en günceli çeker
            if not release_url:
                print(f"⚠️ Özel link bulunamadı, ana sayfadan en güncel sürüm çekiliyor...")
                page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
                sleep_jitter(3)
                latest_release = page.locator("a[href*='-release/']").first
                release_url = f"https://www.apkmirror.com{latest_release.get_attribute('href')}"
                page.goto(release_url, wait_until="domcontentloaded", timeout=30000)
                sleep_jitter(2)
            
            page.wait_for_selector(".table-row", timeout=15000)
            rows = page.locator(".table-row").all()
            
            variant_url = None
            for row in rows:
                text = row.inner_text().lower()
                if "arm64-v8a" in text or "universal" in text or "noarch" in text:
                    link = row.locator("a.accent_color").first
                    if link:
                        variant_url = f"https://www.apkmirror.com{link.get_attribute('href')}"
                        break
                        
            if not variant_url:
                raise Exception("Uygun mimari (arm64-v8a/universal) bulunamadı.")
                
            print(f"➡️ Varyant: {variant_url}")
            page.goto(variant_url, wait_until="domcontentloaded", timeout=30000)
            sleep_jitter(2)
            
            page.wait_for_selector("a.downloadButton", timeout=15000)
            dl_href = page.locator("a.downloadButton").get_attribute("href")
            dl_url = f"https://www.apkmirror.com{dl_href}"
            
            print(f"⬇️ İndirme başlatılıyor...")
            page.goto(dl_url, wait_until="domcontentloaded", timeout=30000)
            
            with page.expect_download(timeout=60000) as dl_info:
                fallback = page.locator("#download-link")
                if fallback.is_visible():
                    fallback.click()
            
            download = dl_info.value
            file_name = f"{app_name}-{download.suggested_filename}"
            file_path = OUT_DIR / file_name
            download.save_as(file_path)
            print(f"📦 BAŞARILI: {file_path}")
            return file_path
            
        except Exception as e:
            print(f"❌ APKMirror Hatası: {str(e)}")
            return None
        finally:
            browser.close()

# --- YAMALAMA ---
def patch_apk(desktop_jar, patches_mpp, apk_path, app_name):
    config = APPS_CONFIG[app_name]
    cmd = [
        "java", "-jar", str(desktop_jar), "patch",
        "--patches", str(patches_mpp),
        "--striplibs", "arm64-v8a"
    ]
    
    ks_path = os.environ.get("KS_PATH")
    if ks_path and Path(ks_path).exists():
        cmd.extend([
            "--keystore", ks_path,
            "--keystore-password", os.environ.get("KS_PASSWORD", ""),
            "--keystore-entry-alias", os.environ.get("KS_ALIAS", ""),
            "--keystore-entry-password", os.environ.get("KEY_PASSWORD", "")
        ])
    
    for ex in config.get("exclude", []):
        cmd.extend(["--disable", ex])
    for en in config.get("enable", []):
        cmd.extend(["--enable", en])
        
    cmd.append(str(apk_path))
    
    try:
        print(f"🖥️ EXECUTING COMMAND: java -jar morphe-desktop ... {apk_path.name}")
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        for line in res.stdout.splitlines():
            if "Saved to" in line:
                patched_apk = Path(line.split("Saved to")[-1].strip())
                final_name = f"{DISPLAY_NAMES[app_name]}-latest.apk"
                final_path = OUT_DIR / final_name
                patched_apk.rename(final_path)
                print(f"✅ Patch done -> {final_name}")
                return final_path
    except subprocess.CalledProcessError as e:
        if "Applying 0 patches" in e.stdout or "Applying 0 patches" in e.stderr:
            print("❌ Uyumlu yama bulunamadı.")
        else:
            print(f"❌ Patch failed:\n{e.stdout}\n{e.stderr}")
    return None

# --- GITHUB RELEASE ---
def create_github_release(tag, name, body, assets):
    print(f"\n📢 Creating New Release: {tag}")
    url = f"https://api.github.com/repos/{REPO}/releases"
    
    payload = {"tag_name": tag, "name": name, "body": body, "draft": False, "prerelease": False}
    res = requests.post(url, headers=get_github_headers(), json=payload)
    res.raise_for_status()
    release = res.json()
    upload_base = release["upload_url"].split("{")[0]
    
    for asset in assets:
        print(f"📤 Upload: {asset.name}")
        headers = get_github_headers()
        headers["Content-Type"] = "application/vnd.android.package-archive"
        upload_url = f"{upload_base}?name={asset.name}"
        with open(asset, "rb") as f:
            requests.post(upload_url, headers=headers, data=f).raise_for_status()
            
    print("🎉 All apps successfully published under one release!")

def main():
    print("🚀 Otomasyon Başlatılıyor...")
    
    desktop = download_github_asset("MorpheApp", "morphe-desktop", ".jar")["path"]
    
    patch_files = {
        "morphe": download_github_asset("MorpheApp", "morphe-patches", ".mpp", True),
        "piko": download_github_asset("crimera", "piko", ".mpp", True),
        "hoodles": download_github_asset("hoo-dles", "morphe-patches", ".mpp", True),
        "adobo": download_github_asset("jkennethcarino", "adobo", ".mpp", True),
        "rushi": download_github_asset("rushiranpise", "morphe-patches", ".mpp", True),
        "bufferk": download_github_asset("bufferk", "morphe-patches", ".mpp", True)
    }

    patched_apks = []
    
    for app in PROCESS_ORDER:
        print(f"\n📦 PROCESSING: {app.upper()}")
        config = APPS_CONFIG[app]
        patch_source = config["patchSource"]
        mpp_file = patch_files[patch_source]["path"]
        
        target_version = get_supported_version(desktop, mpp_file, config["pkg"])
            
        raw_apk = download_from_apkmirror(app, target_version)
        if raw_apk:
            patched = patch_apk(desktop, mpp_file, raw_apk, app)
            if patched:
                patched_apks.append(patched)

    if patched_apks:
        tag = f"build-{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}"
        title = f"Patched APKs · {datetime.now().strftime('%B %d, %Y')}"
        
        body = "### 📦 Latest Patched APKs\n\n"
        for p in patched_apks:
            body += f"* **{p.name.replace('.apk', '')}**\n"
        body += "\n---\n\n"
        
        for p_key, p_data in patch_files.items():
            if p_data["body"]:
                body += f"<details>\n<summary><b>{p_key.capitalize()} Notes ({p_data['tag']})</b></summary>\n<br>\n\n{p_data['body']}\n\n</details>\n"
                
        # MicroG Eklenmesi
        microg = download_github_asset("MorpheApp", "MicroG-RE", ".apk")["path"]
        patched_apks.append(microg)

        create_github_release(tag, title, body, patched_apks)

if __name__ == "__main__":
    main()
