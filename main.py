import os
import sys
import asyncio
import shutil
import traceback
from datetime import datetime
from pathlib import Path

_LIB_DIR = Path(__file__).resolve().parent / "lib"
if _LIB_DIR.is_dir() and str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))

from github import download_latest_github_asset
from versions import extract_youtube_versions
from patcher import patch_apk
from release import ensure_release, upload_patched_apk, upload_microg_once
from verify import verify_apk_signature
import apkmirror

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

APKMIRROR_APPS = [
    "youtube", "youtube-music", "reddit", "twitter",
    "instagram", "niagara-launcher", "github", "smart-launcher",
    "pydroid3", "brave", "wps-office", "solid-explorer"
]

APPS_CONFIG = {
    "youtube": {"pkg": "com.google.android.youtube", "name": "youtube", "patchSource": "morphe", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/youtube/FF0000", "exclude": []},
    "youtube-music": {"pkg": "com.google.android.apps.youtube.music", "name": "youtube-music", "patchSource": "morphe", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/youtubemusic/FF0000", "exclude": []},
    "reddit": {"pkg": "com.reddit.frontpage", "name": "reddit", "patchSource": "morphe", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/reddit/FF4500", "exclude": []},
    "twitter": {"pkg": "com.twitter.android", "name": "twitter", "patchSource": "piko", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/x/000000", "exclude": ["Dynamic color"], "enable": ["Bring back twitter", "Disunify xchat system", "Export all activities"]},
    "instagram": {"pkg": "com.instagram.android", "name": "instagram", "patchSource": "piko", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/instagram/E4405F", "exclude": [], "enable": []},
    "github": {"pkg": "com.github.android", "name": "github", "patchSource": "hoodles", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/github/ffffff", "exclude": []},
    "niagara-launcher": {"pkg": "bitpit.launcher", "name": "niagara-launcher", "patchSource": "hoodles", "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=niagaralauncher.app", "exclude": []},
    "pydroid3": {"pkg": "ru.iiec.pydroid3", "name": "pydroid3", "patchSource": "hoodles", "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=pydroid3.com", "exclude": []},
    "smart-launcher": {"pkg": "ginlemon.flowerfree", "name": "smart-launcher", "patchSource": "hoodles", "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=smartlauncher.net", "exclude": []},
    "wps-office": {"pkg": "cn.wps.moffice_eng", "name": "wps-office", "patchSource": "hoodles", "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=wps.com", "exclude": []},
    "gboard": {"pkg": "com.google.android.inputmethod.latin", "name": "gboard", "patchSource": "adobo", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/google/4285F4", "exclude": [], "enable": ["Enable voice typing in incognito", "Enable key shape selection", "Enable clipboard in incognito", "Enable access points menu redesign", "Enable Undo feature", "Enable OCR feature", "Always-incognito mode"]},
    "speedtest": {"pkg": "org.zwanoo.android.speedtest", "name": "speedtest", "patchSource": "rushi", "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=speedtest.net", "exclude": []},
    "solid-explorer": {"pkg": "pl.solidexplorer2", "name": "solid-explorer", "patchSource": "rushi", "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=solidexplorer.com", "exclude": []},
    "brave": {"pkg": "com.brave.browser", "name": "brave", "patchSource": "bufferk", "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/brave/FB542B", "exclude": []}
}

PROCESS_ORDER = [
    "youtube", "youtube-music", "reddit", "twitter", "instagram",
    "github", "niagara-launcher", "pydroid3", "smart-launcher",
    "wps-office", "solid-explorer", "brave"
    # "gboard" ve "speedtest" şimdilik devre dışı: bu ikisi APK dosyasını
    # GitHub'daki fuckpdf/Depo reposundan (github_dl.py) çekiyor.
    # Sadece patch/desktop-jar dosyaları için GitHub kullanılsın istendiğinden
    # çıkarıldı. Tekrar açmak için bu iki satırı listeye geri ekle.
]

async def process_app(app_key: str, desktop: str, patches: str) -> dict | None:
    config = APPS_CONFIG[app_key]
    print(f"\n📦 PROCESSING: {config['name'].upper()}")

    is_apkmirror_app = config["name"] in APKMIRROR_APPS
    if not is_apkmirror_app:
        raise Exception(
            f'"{config["name"]}" APKMirror listesinde değil ve github_dl kaldırıldığından '
            f"indirilemiyor. APKMIRROR_APPS listesine eklenmeden bu uygulama işlenemez."
        )

    selected_version = config.get("forceVersion")

    if not selected_version:
        try:
            import subprocess
            cmd = ["java", "-jar", desktop, "list-versions", "-f", config["pkg"], f"--patches={patches}", "--include-experimental"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, env={**os.environ, "JAVA_TOOL_OPTIONS": "-Dfile.encoding=UTF8"})
            versions = extract_youtube_versions(result.stdout)
            if versions and len(versions) > 0:
                selected_version = versions[0]["version"]
                print(f"🎯 Patcher önerisi: {selected_version}")
            else:
                print(f"⚠️ list-versions çıktısı parse edilemedi, ham çıktı:\n{result.stdout}")
        except Exception as e:
            print(f"⚠️ Sürüm listesi alınamadı: {e}")

    if not selected_version:
        latest = await apkmirror.get_latest_listing(config["name"])
        if latest and latest.get("version"):
            selected_version = latest["version"]

    if not selected_version:
        raise Exception("Uygun bir sürüm numarası belirlenemedi.")

    apk_path = await apkmirror.download_apk(selected_version, config["name"], config.get("forceBuild"))

    verify_apk_signature(apk_path, config["name"])

    arg_parts = []
    if config.get("exclude"):
        arg_parts.extend([f'--disable "{p}"' for p in config["exclude"]])
    if config.get("enable"):
        arg_parts.extend([f'--enable "{p}"' for p in config["enable"]])

    extra_args = " ".join(arg_parts)
    actual_patched = patch_apk(desktop, patches, apk_path, extra_args, config["arch"])

    if not Path(actual_patched).exists():
        return None

    app_display_name = DISPLAY_NAMES.get(config["name"], config["name"])
    final_name = f"{app_display_name}-{selected_version}.apk"
    final_path = Path.cwd() / final_name

    shutil.copy2(actual_patched, final_path)

    return {
        "appName": config["name"],
        "displayName": app_display_name,
        "icon": config["icon"],
        "patchSource": config["patchSource"],
        "name": final_name,
        "path": str(final_path),
        "version": selected_version
    }

async def main():
    try:
        print("🚀 Starting Morphe Patcher (Python Edition)")

        desktop_obj = await download_latest_github_asset(
            owner="MorpheApp", repo="morphe-desktop",
            prerelease=True,
            match_fn=lambda n: "desktop" in n and n.endswith(".jar")
        )
        desktop = desktop_obj["name"]

        patches_pool = {"morphe": None, "piko": None, "hoodles": None, "adobo": None, "rushi": None, "bufferk": None}
        notes = {"morphe": "", "piko": "", "hoodles": "", "adobo": "", "rushi": "", "bufferk": ""}

        target_app = os.getenv("TARGET_APP", "all")
        apps_to_process = PROCESS_ORDER if target_app == "all" else [target_app]

        patch_sources = {
            "morphe": ("MorpheApp", "morphe-patches", "🟢"),
            "piko": ("crimera", "piko", "✖️"),
            "hoodles": ("hoo-dles", "morphe-patches", "🍃"),
            "adobo": ("jkennethcarino", "adobo", "🥘"),
            "rushi": ("rushiranpise", "morphe-patches", "⚡"),
            "bufferk": ("bufferk", "morphe-patches", "🟣")
        }

        for source, (owner, repo, emoji) in patch_sources.items():
            if any(APPS_CONFIG[k]["patchSource"] == source for k in apps_to_process):
                mpp = await download_latest_github_asset(owner=owner, repo=repo, prerelease=True, match_fn=lambda n: n.endswith(".mpp"))
                patches_pool[source] = mpp["name"]
                notes[source] = f"\n<details>\n<summary>{emoji} <b>{source.capitalize()} Release Notes ({mpp['tag']})</b></summary>\n<br>\n\n{mpp['body']}\n\n</details>\n"

        patched_apks_list = []
        for app_key in apps_to_process:
            try:
                source = APPS_CONFIG[app_key]["patchSource"]
                result = await process_app(app_key, desktop, patches_pool[source])
                if result:
                    patched_apks_list.append(result)
            except Exception as err:
                print(f"❌ {app_key.upper()} failed, skipping:")
                traceback.print_exc()

        if patched_apks_list:
            now = datetime.now()
            tag_date_str = now.isoformat().replace(":", "-").replace(".", "-")[:19]
            release_tag = f"build-{tag_date_str}"
            release_name = f"Patched APKs · {now.strftime('%d %B %Y')}"

            unified_body = "### 📦 Latest Patched APKs\n\n"
            for apk in patched_apks_list:
                unified_body += f"* <img src=\"{apk['icon']}\" width=\"16\" height=\"16\"> **{apk['displayName']}**\n"
            unified_body += "\n---\n\n"

            for source in ["morphe", "piko", "hoodles", "adobo", "rushi", "bufferk"]:
                if notes[source]:
                    unified_body += notes[source]

            print(f"\n📢 Creating New Release: {release_tag}")
            release = await ensure_release(release_tag, release_name, unified_body)

            uploaded_names = set()
            for apk in patched_apks_list:
                try:
                    await upload_patched_apk(release, apk["path"])
                    uploaded_names.add(apk["appName"])
                except Exception as up_err:
                    print(f"⚠️ {apk['name']} yüklenemedi (release'e eklenemedi): {up_err}")

            if {"youtube", "youtube-music"} & uploaded_names:
                try:
                    await upload_microg_once(release)
                except Exception as mg_err:
                    print(f"⚠️ MicroG yüklenemedi: {mg_err}")

            print("\n🎉 All apps successfully published under one release!")

    except Exception as err:
        print(f"❌ Fatal error: {err}")
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())
