import os
import sys
import time
import json
import random
import requests
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

# --- AYARLAR VE YAPILANDIRMA ---

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
    "brave": "Brave"
}

APPS_CONFIG = {
    "youtube": {
        "pkg": "com.google.android.youtube",
        "patchSource": "morphe",
        "am_url": "https://www.apkmirror.com/apk/google-inc/youtube/"
    },
    "youtube-music": {
        "pkg": "com.google.android.apps.youtube.music",
        "patchSource": "morphe",
        "am_url": "https://www.apkmirror.com/apk/google-inc/youtube-music/"
    },
    "reddit": {
        "pkg": "com.reddit.frontpage",
        "patchSource": "morphe",
        "am_url": "https://www.apkmirror.com/apk/reddit-inc/reddit/"
    },
    "twitter": {
        "pkg": "com.twitter.android",
        "patchSource": "piko",
        "am_url": "https://www.apkmirror.com/apk/x-corp/twitter/",
        "exclude": ["Dynamic color"],
        "enable": ["Bring back twitter", "Disunify xchat system", "Export all activities"]
    },
    "instagram": {
        "pkg": "com.instagram.android",
        "patchSource": "piko",
        "am_url": "https://www.apkmirror.com/apk/instagram/instagram-instagram/"
    },
    "github": {
        "pkg": "com.github.android",
        "patchSource": "hoodles",
        "am_url": "https://www.apkmirror.com/apk/github/github-2/"
    },
    "niagara-launcher": {
        "pkg": "bitpit.launcher",
        "patchSource": "hoodles",
        "am_url": "https://www.apkmirror.com/apk/mellowdrop-studio/niagara-launcher-%f0%9f%94%b9-fresh-clean/"
    },
    "pydroid3": {
        "pkg": "ru.iiec.pydroid3",
        "patchSource": "hoodles",
        "am_url": "https://www.apkmirror.com/apk/lider-soft-kz/pydroid-3-ide-for-python-3/"
    },
    "smart-launcher": {
        "pkg": "ginlemon.flowerfree",
        "patchSource": "hoodles",
        "am_url": "https://www.apkmirror.com/apk/smart-launcher-team/smart-launcher/"
    },
    "wps-office": {
        "pkg": "cn.wps.moffice_eng",
        "patchSource": "hoodles",
        "am_url": "https://www.apkmirror.com/apk/wps-software-pte-ltd/wps-office-pdf/"
    },
    "gboard": {
        "pkg": "com.google.android.inputmethod.latin",
        "patchSource": "adobo",
        "am_url": "https://www.apkmirror.com/apk/google-inc/gboard/",
        "enable": ["Enable voice typing in incognito", "Enable key shape selection", "Enable clipboard in incognito", "Enable access points menu redesign", "Enable Undo feature", "Enable OCR feature", "Always-incognito mode"]
    },
    "speedtest": {
        "pkg": "org.zwanoo.android.speedtest",
        "patchSource": "rushi",
        "am_url": "https://www.apkmirror.com/apk/ookla/speedtest/"
    },
    "solid-explorer": {
        "pkg": "pl.solidexplorer2",
        "patchSource": "rushi",
        "am_url": "https://www.apkmirror.com/apk/neatbytes/solid-explorer-file-manager/"
    },
    "brave": {
        "pkg": "com.brave.browser",
        "patchSource": "bufferk",
        "am_url": "https://www.apkmirror.com/apk/brave-software/brave-browser/"
    }
}

OUT_DIR = Path("downloads")
OUT_DIR.mkdir(exist_ok=True)

# --- YARDIMCI FONKSİYONLAR ---

def sleep_jitter(base=2):
    """Bot engellemesine karşı rastgele bekleme süresi."""
    delay = base + random.uniform(0.5, 2.5)
    time.sleep(delay)

def get_latest_github_release(owner, repo):
    """GitHub API'den en son sürüm asset'ini çeker."""
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    headers = {"Accept": "application/vnd.github+json"}
    
    if "GITHUB_TOKEN" in os.environ:
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
        
    res = requests.get(url, headers=headers)
    res.raise_for_status()
    return res.json()

def download_file(url, out_path):
    """Standart dosya indirme."""
    print(f"⬇️ İndiriliyor: {out_path.name}")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(out_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return out_path

# --- APKMIRROR SCRAPER ---

def download_from_apkmirror(app_name):
    """Playwright + Stealth ile APKMirror üzerinden indirme yapar."""
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
        stealth_sync(page)  # Bot korumasını aşmak için
        
        try:
            print(f"🌐 Ziyaret ediliyor: {base_url}")
            page.goto(base_url, wait_until="domcontentloaded")
            sleep_jitter(3)
            
            # 1. En güncel sürümün bağlantısını bul (Release sayfası)
            latest_release_element = page.locator("a[href*='-release/']").first
            release_url = f"https://www.apkmirror.com{latest_release_element.get_attribute('href')}"
            print(f"➡️ Sürüm Sayfası: {release_url}")
            
            page.goto(release_url, wait_until="domcontentloaded")
            sleep_jitter(2)
            
            # 2. Uygun varyantı (arm64-v8a veya universal) seç
            page.wait_for_selector(".table-row", timeout=15000)
            rows = page.locator(".table-row").all()
            
            variant_url = None
            for row in rows:
                text = row.inner_text().lower()
                # Mimari kontrolleri
                if "arm64-v8a" in text or "universal" in text or "noarch" in text:
                    link = row.locator("a.accent_color").first
                    if link:
                        variant_url = f"https://www.apkmirror.com{link.get_attribute('href')}"
                        break
                        
            if not variant_url:
                raise Exception("Uygun bir arm64-v8a veya universal varyant bulunamadı.")
                
            print(f"➡️ Varyant Sayfası: {variant_url}")
            page.goto(variant_url, wait_until="domcontentloaded")
            sleep_jitter(2)
            
            # 3. İndirme sayfasına git
            page.wait_for_selector("a.downloadButton", timeout=15000)
            download_page_href = page.locator("a.downloadButton").get_attribute("href")
            download_url = f"https://www.apkmirror.com{download_page_href}"
            
            print(f"⬇️ İndirme başlatılıyor...")
            page.goto(download_url, wait_until="domcontentloaded")
            
            # 4. Asıl indirmeyi yakala
            with page.expect_download(timeout=45000) as download_info:
                # İndirme genellikle otomatik başlar, başlamazsa 'download-link' fallback
                fallback_link = page.locator("#download-link")
                if fallback_link.is_visible():
                    fallback_link.click()
            
            download = download_info.value
            file_name = download.suggested_filename
            file_path = OUT_DIR / file_name
            download.save_as(file_path)
            
            print(f"📦 BAŞARILI: {file_path}")
            return file_path
            
        except Exception as e:
            print(f"❌ APKMirror Hatası ({app_name}): {str(e)}")
            return None
        finally:
            browser.close()

# --- YAMALAMA SÜRECİ ---

def patch_apk(desktop_jar, patches_mpp, apk_path, app_name):
    """Morphe Java aracı ile APK'yı yamalar."""
    config = APPS_CONFIG[app_name]
    print(f"\n🛠️ Patching APK ({app_name.upper()})...")
    
    cmd = [
        "java", "-jar", str(desktop_jar), "patch",
        "--patches", str(patches_mpp),
        "--striplibs", "arm64-v8a"
    ]
    
    # Keystore kontrolü
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
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        # Çıktıdan yeni APK yolunu bul
        for line in result.stdout.splitlines():
            if "Saved to" in line:
                patched_apk = line.split("Saved to")[-1].strip()
                print(f"✅ Patch tamamlandı: {patched_apk}")
                return Path(patched_apk)
    except subprocess.CalledProcessError as e:
        print(f"❌ Yama başarısız oldu:\n{e.stdout}\n{e.stderr}")
    return None

# --- ANA DÖNGÜ ---

def main():
    print("🚀 Otomasyon Başlatılıyor...")
    
    # Gerekli yamalayıcı araçlarını indir (Basitleştirilmiş gösterim, morphe-desktop.jar'ı yerel kabul eder)
    # Gerçek senaryoda burada get_latest_github_release ile morphe-desktop ve patch dosyalarını (piko.mpp vb.) çekmelisin.
    desktop_jar = Path("morphe-desktop-1.11.0-all.jar") 
    
    # Yama (mpp) dosyalarının bulunduğu varsayılan sözlük
    patches = {
        "morphe": Path("morphe.mpp"),
        "piko": Path("piko.mpp"),
        "hoodles": Path("hoodles.mpp"),
        "adobo": Path("adobo.mpp"),
        "rushi": Path("rushi.mpp"),
        "bufferk": Path("bufferk.mpp")
    }

    target_app = os.environ.get("TARGET_APP", "all")
    apps_to_process = list(APPS_CONFIG.keys()) if target_app == "all" else [target_app]

    for app in apps_to_process:
        print(f"\n========================================")
        print(f"📦 İŞLEM: {DISPLAY_NAMES.get(app, app)}")
        
        apk_path = download_from_apkmirror(app)
        if apk_path and apk_path.exists():
            patch_source = APPS_CONFIG[app]["patchSource"]
            patch_file = patches.get(patch_source)
            
            if patch_file and patch_file.exists():
                patched_file = patch_apk(desktop_jar, patch_file, apk_path, app)
                if patched_file:
                    print(f"🎉 {app.upper()} başarıyla hazırlandı!")
            else:
                print(f"⚠️ Yama dosyası bulunamadı: {patch_file}")

if __name__ == "__main__":
    main()
