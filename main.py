import os
from pathlib import Path
from datetime import datetime

from lib.apkmirror import download_apk
from lib.github import download_asset
from lib.patcher import patch_apk
from lib.release import create_github_release

OUT_DIR = Path("downloads")
OUT_DIR.mkdir(exist_ok=True)

DISPLAY_NAMES = {
    "youtube": "YouTube", "youtube-music": "YT.Music", "reddit": "Reddit",
    "twitter": "Twitter", "instagram": "Instagram", "github": "GitHub",
    "niagara-launcher": "Niagara Launcher", "pydroid3": "PyDroid3",
    "smart-launcher": "Smart Launcher", "wps-office": "WPS Office",
    "gboard": "Gboard", "speedtest": "Speedtest",
    "solid-explorer": "Solid Explorer", "brave": "Brave"
}

APPS_CONFIG = {
    "youtube": {"patchSource": "morphe", "am_url": "https://www.apkmirror.com/apk/google-inc/youtube/"},
    "youtube-music": {"patchSource": "morphe", "am_url": "https://www.apkmirror.com/apk/google-inc/youtube-music/"},
    "reddit": {"patchSource": "morphe", "am_url": "https://www.apkmirror.com/apk/reddit-inc/reddit/"},
    "twitter": {"patchSource": "piko", "am_url": "https://www.apkmirror.com/apk/x-corp/twitter/", "exclude": ["Dynamic color"], "enable": ["Bring back twitter", "Disunify xchat system", "Export all activities"]},
    "instagram": {"patchSource": "piko", "am_url": "https://www.apkmirror.com/apk/instagram/instagram-instagram/"},
    "github": {"patchSource": "hoodles", "am_url": "https://www.apkmirror.com/apk/github/github-2/"},
    "niagara-launcher": {"patchSource": "hoodles", "am_url": "https://www.apkmirror.com/apk/mellowdrop-studio/niagara-launcher-%f0%9f%94%b9-fresh-clean/"},
    "pydroid3": {"patchSource": "hoodles", "am_url": "https://www.apkmirror.com/apk/lider-soft-kz/pydroid-3-ide-for-python-3/"},
    "smart-launcher": {"patchSource": "hoodles", "am_url": "https://www.apkmirror.com/apk/smart-launcher-team/smart-launcher/"},
    "wps-office": {"patchSource": "hoodles", "am_url": "https://www.apkmirror.com/apk/wps-software-pte-ltd/wps-office-pdf/"},
    "gboard": {"patchSource": "adobo", "am_url": "https://www.apkmirror.com/apk/google-inc/gboard/", "enable": ["Enable voice typing in incognito", "Enable key shape selection", "Enable clipboard in incognito", "Enable access points menu redesign", "Enable Undo feature", "Enable OCR feature", "Always-incognito mode"]},
    "speedtest": {"patchSource": "rushi", "am_url": "https://www.apkmirror.com/apk/ookla/speedtest/"},
    "solid-explorer": {"patchSource": "rushi", "am_url": "https://www.apkmirror.com/apk/neatbytes/solid-explorer-file-manager/"},
    "brave": {"patchSource": "bufferk", "am_url": "https://www.apkmirror.com/apk/brave-software/brave-browser/"}
}

def main():
    print("🚀 Otomasyon Başlatılıyor...")
    
    desktop = download_asset("MorpheApp", "morphe-desktop", ".jar")["path"]
    patch_files = {
        "morphe": download_asset("MorpheApp", "morphe-patches", ".mpp", True),
        "piko": download_asset("crimera", "piko", ".mpp", True),
        "hoodles": download_asset("hoo-dles", "morphe-patches", ".mpp", True),
        "adobo": download_asset("jkennethcarino", "adobo", ".mpp", True),
        "rushi": download_asset("rushiranpise", "morphe-patches", ".mpp", True),
        "bufferk": download_asset("bufferk", "morphe-patches", ".mpp", True)
    }

    patched_apks = []
    
    for app, config in APPS_CONFIG.items():
        print(f"\n📦 PROCESSING: {app.upper()}")
        raw_apk = download_apk(app, config, OUT_DIR)
        
        if raw_apk:
            mpp_file = patch_files[config["patchSource"]]["path"]
            patched = patch_apk(desktop, mpp_file, raw_apk, config, app, DISPLAY_NAMES[app], OUT_DIR)
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
                
        # MicroG Ekle
        microg = download_asset("MorpheApp", "MicroG-RE", ".apk")["path"]
        patched_apks.append(microg)

        create_github_release(tag, title, body, patched_apks)

if __name__ == "__main__":
    # '__init__.py' dosyasını oluşturarak lib klasörünü bir paket haline getir.
    Path("lib/__init__.py").touch(exist_ok=True)
    main()
