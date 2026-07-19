import os
import shutil
import subprocess
from datetime import datetime
from lib.github import download_latest_github_asset
from lib.versions import extract_youtube_versions, pick_latest_version
from lib.patcher import patch_apk
from lib.release import ensure_release, upload_patched_apk, upload_microg_once
import lib.apkmirror as apkmirror
import lib.githubdl as githubdl

DISPLAY_NAMES = {
    "youtube": "YouTube", "youtube-music": "YT.Music", "reddit": "Reddit",
    "twitter": "Twitter", "instagram": "Instagram", "github": "GitHub",
    "niagara-launcher": "Niagara Launcher", "pydroid3": "PyDroid3",
    "smart-launcher": "Smart Launcher", "wps-office": "WPS Office",
    "gboard": "Gboard", "speedtest": "Speedtest", "solid-explorer": "Solid Explorer",
    "brave": "Brave"
}

APKMIRROR_APPS = ["youtube", "youtube-music", "reddit", "twitter"]

APPS_CONFIG = {
    "youtube": {"pkg": "com.google.android.youtube", "name": "youtube", "patchSource": "morphe", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/youtube/FF0000", "exclude": []},
    "youtube-music": {"pkg": "com.google.android.apps.youtube.music", "name": "youtube-music", "patchSource": "morphe", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/youtubemusic/FF0000", "exclude": []},
    "reddit": {"pkg": "com.reddit.frontpage", "name": "reddit", "patchSource": "morphe", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/reddit/FF4500", "exclude": []},
    "twitter": {"pkg": "com.twitter.android", "name": "twitter", "patchSource": "piko", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/x/000000", "exclude": ["Dynamic color"], "enable": ["Bring back twitter", "Disunify xchat system", "Export all activities"]},
    "instagram": {"pkg": "com.instagram.android", "name": "instagram", "patchSource": "piko", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/instagram/E4405F", "exclude": [], "forceVersion": "435.0.0.37.76", "forceBuild": "384109456"},
    "github": {"pkg": "com.github.android", "name": "github", "patchSource": "hoodles", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/github/ffffff", "exclude": []},
    "niagara-launcher": {"pkg": "bitpit.launcher", "name": "niagara-launcher", "patchSource": "hoodles", "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=niagaralauncher.app", "exclude": [], "forceVersion": "1.16.8"},
    "pydroid3": {"pkg": "ru.iiec.pydroid3", "name": "pydroid3", "patchSource": "hoodles", "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=pydroid3.com", "exclude": []},
    "smart-launcher": {"pkg": "ginlemon.flowerfree", "name": "smart-launcher", "patchSource": "hoodles", "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=smartlauncher.net", "exclude": []},
    "wps-office": {"pkg": "cn.wps.moffice_eng", "name": "wps-office", "patchSource": "hoodles", "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=wps.com", "exclude": []},
    "gboard": {"pkg": "com.google.android.inputmethod.latin", "name": "gboard", "patchSource": "adobo", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/google/4285F4", "exclude": [], "enable": ["Enable voice typing in incognito", "Enable key shape selection", "Enable clipboard in incognito", "Enable access points menu redesign", "Enable Undo feature", "Enable OCR feature", "Always-incognito mode"]},
    "speedtest": {"pkg": "org.zwanoo.android.speedtest", "name": "speedtest", "patchSource": "rushi", "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=speedtest.net", "exclude": [], "forceVersion": "7.0.7"},
    "solid-explorer": {"pkg": "pl.solidexplorer2", "name": "solid-explorer", "patchSource": "rushi", "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=solidexplorer.com", "exclude": []},
    "brave": {"pkg": "com.brave.browser", "name": "brave", "patchSource": "bufferk", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/brave/FB542B", "exclude": []}
}

PROCESS_ORDER = ["youtube", "youtube-music", "reddit", "twitter", "instagram", "github", "niagara-launcher", "pydroid3", "smart-launcher", "wps-office", "gboard", "speedtest", "solid-explorer", "brave"]

def process_app(app_key: str, desktop: str, patches: str):
    config = APPS_CONFIG[app_key]
    print(f"\nPROCESSING: {config['name'].upper()}")
    
    is_apkmirror = config["name"] in APKMIRROR_APPS
    selected_version = config.get("forceVersion")
    
    if not selected_version:
        try:
            out = subprocess.run(["java", "-jar", desktop, "list-versions", "-f", config["pkg"], f"--patches={patches}", "--include-experimental"], capture_output=True, text=True, check=True)
            versions = extract_youtube_versions(out.stdout)
            if versions:
                selected_version = pick_latest_version(versions)
        except Exception as e:
            print(f"Error fetching version list: {e}")
            
    if not selected_version:
        if not is_apkmirror:
            selected_version = "latest"
        else:
            latest = apkmirror.get_latest_listing(config["name"])
            if latest:
                selected_version = latest["version"]
                
    if not selected_version:
        raise Exception("Version not found")

    if is_apkmirror:
        apk_path = apkmirror.download_apk(selected_version, config["name"], config.get("forceBuild"))
    else:
        apk_path = githubdl.download_apk(selected_version, config["name"])
        
    args_list = []
    for ex in config.get("exclude", []):
        args_list.extend(["--disable", f'"{ex}"'])
    for en in config.get("enable", []):
        args_list.extend(["--enable", f'"{en}"'])
    extra_args = " ".join(args_list)
    
    patched_path = patch_apk(desktop, patches, apk_path, extra_args, config["arch"])
    if not os.path.exists(patched_path):
        return None
        
    display_name = DISPLAY_NAMES.get(config["name"], config["name"])
    final_name = f"{display_name}-{selected_version}.apk"
    final_path = os.path.abspath(final_name)
    shutil.copyfile(patched_path, final_path)
    
    return {
        "appName": config["name"],
        "displayName": display_name,
        "icon": config.get("icon", ""),
        "path": final_path
    }

def main():
    desktop_obj = download_latest_github_asset("MorpheApp", "morphe-desktop", lambda n: "desktop" in n and n.endswith(".jar"))
    desktop = desktop_obj["name"]
    
    target_app = os.environ.get("TARGET_APP", "all")
    apps = PROCESS_ORDER if target_app == "all" else [target_app]
    
    patches_pool = {}
    notes_pool = {}
    
    sources = [
        ("morphe", "MorpheApp", "morphe-patches", "🟢", "Morphe"),
        ("piko", "crimera", "piko", "✖️", "Piko"),
        ("hoodles", "hoo-dles", "morphe-patches", "🍃", "hoo-dles"),
        ("adobo", "jkennethcarino", "adobo", "🥘", "Adobo"),
        ("rushi", "rushiranpise", "morphe-patches", "⚡", "Rushiranpise"),
        ("bufferk", "bufferk", "morphe-patches", "🟣", "Bufferk"),
    ]
    
    for key, owner, repo, emoji, name in sources:
        if any(APPS_CONFIG[a].get("patchSource") == key for a in apps):
            asset = download_latest_github_asset(owner, repo, lambda n: n.endswith(".mpp"), True)
            patches_pool[key] = asset["name"]
            notes_pool[key] = f"\n<details>\n<summary>{emoji} <b>{name} Release Notes ({asset['tag']})</b></summary>\n<br>\n\n{asset['body']}\n\n</details>\n"
            
    patched_list = []
    for app_key in apps:
        config = APPS_CONFIG[app_key]
        p_file = patches_pool.get(config["patchSource"])
        if not p_file:
            continue
        try:
            res = process_app(app_key, desktop, p_file)
            if res:
                patched_list.append(res)
        except Exception as e:
            print(f"Failed {app_key}: {e}")
            
    if patched_list:
        dt_str = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
        tag = f"build-{dt_str}"
        r_name = f"Patched APKs · {datetime.utcnow().strftime('%B %d, %Y')}"
        
        body = "### 📦 Latest Patched APKs\n\n"
        for apk in patched_list:
            body += f'* <img src="{apk["icon"]}" width="16" height="16"> **{apk["displayName"]}**\n'
        body += "\n---\n\n"
        
        for k, owner, repo, emoji, name in sources:
            if k in notes_pool:
                body += notes_pool[k]
                
        release = ensure_release(tag, r_name, body)
        microg_uploaded = False
        for apk in patched_list:
            upload_patched_apk(release, apk["path"])
            if not microg_uploaded and apk["appName"] in ["youtube", "youtube-music"]:
                upload_microg_once(release)
                microg_uploaded = True

if __name__ == "__main__":
    main()
