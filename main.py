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
    "instagram": {"pkg": "com.instagram.android", "patchSource": "piko", "am_url": "https://www.apkmirror.com/apk/instagram/instagram-instagram/", "releaseSlug": "instagram"},
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

def get_supported_versions(desktop_jar, patches_mpp, pkg_name):
    """Artık tek bir sürüm değil, desteklenen TÜM sürümleri liste olarak döndürür."""
    try:
        cmd = ["java", "-jar", str(desktop_jar), "list-versions", "-f", pkg_name, "--patches", str(patches_mpp), "--include-experimental"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        versions = [m.group(1) for line in res.stdout.splitlines() for m in [re.search(r'(\d+(?:\.\d+)+)', line)] if m]
        if versions:
            # Büyükten küçüğe sıralı tüm sürümleri döndür
            return sorted(list(set(versions)), key=lambda s: [int(u) for u in s.split('.') if u.isdigit()], reverse=True)
    except: pass
    return []

def download_apk(app_name, config, out_dir, target_versions):
    base_url = config["am_url"]
    
    if not target_versions:
        print(f"[{app_name}] ⚠️ Uyarı: Yama dosyası bu uygulama için sürüm önermedi, en son sürüm deneniyor.")
        target_versions = [None]
    else:
        print(f"[{app_name}] 🎯 Desteklenen yama sürümleri sırayla denenecek: {target_versions}")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        page = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
            accept_downloads=True
        ).new_page()
        stealth_sync(page)
        try:
            release_url = None
            
            # Sürümleri sırayla dene (İlk bulduğunu indirecek)
            for target_version in target_versions:
                if target_version:
                    v_slug = target_version.replace(".", "-")
                    name_part = config.get("releaseSlug", base_url.rstrip('/').split('/')[-1])
                    for c in [f"{base_url}{name_part}-{v_slug}-{s}/" for s in ["release", "release-0-release", "beta-0-release", "beta-1-release", "alpha-0-release"]]:
                        try:
                            res = page.goto(c, wait_until="domcontentloaded", timeout=10000)
                            if res and res.status != 404 and page.locator(".table-row").count() > 0:
                                release_url = c
                                print(f"[{app_name}] ✅ Uygun sürüm bulundu: {target_version} -> {release_url}")
                                break
                        except: continue
                    if release_url:
                        break # Sürüm bulundu, döngüden çık
                else:
                    # Sürüm listesi boşsa en son sürüme git
                    page.goto(base_url, wait_until="domcontentloaded", timeout=45000)
                    latest = page.locator("a[href*='-release/']").first
                    release_url = f"https://www.apkmirror.com{latest.get_attribute('href')}"
                    page.goto(release_url, wait_until="domcontentloaded", timeout=45000)
                    break

            if not release_url:
                print(f"[{app_name}] ❌ HATA: Denenen hiçbir sürüm APKMirror'da bulunamadı. Bu uygulama atlanıyor.")
                return None
            
            page.wait_for_selector(".table-row", timeout=20000)
            for row in page.locator(".table-row").all():
                if any(x in row.inner_text().lower() for x in ["arm64-v8a", "universal", "noarch"]):
                    variant_url = f"https://www.apkmirror.com{row.locator('a.accent_color').first.get_attribute('href')}"
                    page.goto(variant_url, wait_until="domcontentloaded")
                    break
            
            page.wait_for_selector("a.downloadButton", timeout=20000)
            download_page_url = f"https://www.apkmirror.com{page.locator('a.downloadButton').get_attribute('href')}"
            page.goto(download_page_url, wait_until="domcontentloaded")
            
            page.wait_for_selector("#download-link", timeout=20000)
            print(f"[{app_name}] APK/Bundle indiriliyor (Bot koruması atlatılıyor)...")
            
            with page.expect_download(timeout=120000) as download_info:
                page.locator("#download-link").click()
                
            download = download_info.value
            
            original_ext = Path(download.suggested_filename).suffix
            if not original_ext:
                original_ext = ".apk"
                
            path = out_dir / f"{app_name}{original_ext}"
            download.save_as(path)
            
            print(f"[{app_name}] ✅ İndirme başarılı: {path}")
            return path
        except Exception as e:
            print(f"[{app_name}] ❌ İndirme sırasında bir hata oluştu: {e}")
            return None
        finally: 
            browser.close()

def patch_apk(desktop_jar, patches_mpp, apk_path, app_name):
    config = APPS_CONFIG[app_name]
    final_path = OUT_DIR / f"{DISPLAY_NAMES[app_name]}-latest.apk"
    
    cmd = ["java", "-jar", str(desktop_jar), "patch", "--patches", str(patches_mpp), "--striplibs", "arm64-v8a", "--out", str(final_path)]
    
    ks = os.environ.get("KS_PATH")
    if ks and Path(ks).exists():
        cmd.extend(["--keystore", ks, "--keystore-password", os.environ.get("KS_PASSWORD", ""), "--keystore-entry-alias", os.environ.get("KS_ALIAS", ""), "--keystore-entry-password", os.environ.get("KEY_PASSWORD", "")])
        
    for ex in config.get("exclude", []): cmd.extend(["--disable", ex])
    for en in config.get("enable", []): cmd.extend(["--enable", en])
    
    cmd.append(str(apk_path))
    
    print(f"[{app_name}] Yama işlemi başlatılıyor...")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        if final_path.exists():
            print(f"[{app_name}] ✅ Yama BAŞARILI: {final_path}")
            return final_path
        else:
            print(f"[{app_name}] ⚠️ Uyarı: Patcher hata vermedi ama '{final_path}' dosyası da oluşmadı!")
            return None
    except subprocess.CalledProcessError as e:
        print(f"[{app_name}] ❌ Yama BAŞARISIZ! (Hata Kodu: {e.returncode})")
        print(f"[{app_name}] --- STDOUT (Çıktı) ---\n{e.stdout}")
        print(f"[{app_name}] --- STDERR (Hata) ---\n{e.stderr}")
        return None
    except Exception as e:
        print(f"[{app_name}] ❌ Beklenmeyen Yama Hatası: {e}")
        return None

def create_release(tag, name, body, assets):
    res = requests.post(f"https://api.github.com/repos/{REPO}/releases", headers=get_github_headers(), json={"tag_name": tag, "name": name, "body": body})
    res.raise_for_status()
    upload_url = res.json()["upload_url"].split("{")[0]
    for asset in assets:
        requests.post(f"{upload_url}?name={asset.name}", headers={**get_github_headers(), "Content-Type": "application/vnd.android.package-archive"}, data=open(asset, "rb")).raise_for_status()

def main():
    desktop = download_asset("MorpheApp", "morphe-desktop", ".jar", True)["path"]
    
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
        
        # Desteklenen TÜM sürümlerin listesini alıyoruz
        target_versions = get_supported_versions(desktop, mpp, config["pkg"])
        
        # Listeyi sırayla deneyerek indir
        raw = download_apk(app, config, OUT_DIR, target_versions)
        
        if raw:
            patched = patch_apk(desktop, mpp, raw, app)
            if patched: patched_apks.append(patched)
            
    if patched_apks:
        print(f"\n🎉 Toplam {len(patched_apks)} APK başarıyla yamalandı. Release oluşturuluyor...")
        tag = f"build-{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}"
        body = "### Latest Patched APKs\n" + "\n".join([f"* {p.name}" for p in patched_apks])
        
        try:
            patched_apks.append(download_asset("MorpheApp", "MicroG-RE", ".apk", True)["path"])
        except:
            print("Uyarı: MicroG indirilemedi.")
            
        create_release(tag, f"Patched APKs {datetime.now().strftime('%Y-%m-%d')}", body, patched_apks)
    else:
        print("\n⚠️ Hiçbir APK yamalanamadığı için Release işlemi atlandı!")

if __name__ == "__main__":
    main()
