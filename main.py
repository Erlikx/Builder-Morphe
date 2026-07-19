import os
import sys
import shutil
import logging
import asyncio
from pathlib import Path
from datetime import datetime

from lib.github import download_latest_github_asset
from lib.apkmirror import download_apk, get_latest_listing
from lib.patcher import patch_apk
from lib.release import ensure_release, upload_patched_apk, upload_microg_once
from lib.versions import extract_youtube_versions, pick_latest_version

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
        "name": "youtube",
        "patch_source": "morphe",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/youtube/FF0000",
        "exclude": []
    },
    "youtube-music": {
        "pkg": "com.google.android.apps.youtube.music",
        "name": "youtube-music",
        "patch_source": "morphe",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/youtubemusic/FF0000",
        "exclude": []
    },
    "reddit": {
        "pkg": "com.reddit.frontpage",
        "name": "reddit",
        "patch_source": "morphe",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/reddit/FF4500",
        "exclude": []
    },
    "twitter": {
        "pkg": "com.twitter.android",
        "name": "twitter",
        "patch_source": "piko",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/x/000000",
        "exclude": ["Dynamic color"],
        "enable": ["Bring back twitter", "Disunify xchat system", "Export all activities"]
    },
    "instagram": {
        "pkg": "com.instagram.android",
        "name": "instagram",
        "patch_source": "piko",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/instagram/E4405F",
        "exclude": [],
        "enable": [],
        "force_version": "435.0.0.37.76",
        "force_build": "384109456"
    },
    "github": {
        "pkg": "com.github.android",
        "name": "github",
        "patch_source": "hoodles",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/github/ffffff",
        "exclude": []
    },
    "niagara-launcher": {
        "pkg": "bitpit.launcher",
        "name": "niagara-launcher",
        "patch_source": "hoodles",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=niagaralauncher.app",
        "exclude": [],
        "force_version": "1.16.8"
    },
    "pydroid3": {
        "pkg": "ru.iiec.pydroid3",
        "name": "pydroid3",
        "patch_source": "hoodles",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=pydroid3.com",
        "exclude": []
    },
    "smart-launcher": {
        "pkg": "ginlemon.flowerfree",
        "name": "smart-launcher",
        "patch_source": "hoodles",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=smartlauncher.net",
        "exclude": []
    },
    "wps-office": {
        "pkg": "cn.wps.moffice_eng",
        "name": "wps-office",
        "patch_source": "hoodles",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=wps.com",
        "exclude": []
    },
    "gboard": {
        "pkg": "com.google.android.inputmethod.latin",
        "name": "gboard",
        "patch_source": "adobo",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/google/4285F4",
        "exclude": [],
        "enable": ["Enable voice typing in incognito", "Enable key shape selection", "Enable clipboard in incognito", "Enable access points menu redesign", "Enable Undo feature", "Enable OCR feature", "Always-incognito mode"]
    },
    "speedtest": {
        "pkg": "org.zwanoo.android.speedtest",
        "name": "speedtest",
        "patch_source": "rushi",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=speedtest.net",
        "exclude": [],
        "force_version": "7.0.7"
    },
    "solid-explorer": {
        "pkg": "pl.solidexplorer2",
        "name": "solid-explorer",
        "patch_source": "rushi",
        "arch": "arm64-v8a",
        "icon": "https://www.google.com/s2/favicons?sz=128&domain=solidexplorer.com",
        "exclude": []
    },
    "brave": {
        "pkg": "com.brave.browser",
        "name": "brave",
        "patch_source": "bufferk",
        "arch": "arm64-v8a",
        "icon": "https://cdn.simpleicons.org/brave/FB542B",
        "exclude": []
    }
}

PROCESS_ORDER = [
    "youtube",
    "youtube-music",
    "reddit",
    "twitter",
    "instagram",
    "github",
    "niagara-launcher",
    "pydroid3",
    "smart-launcher",
    "wps-office",
    "gboard",
    "speedtest",
    "solid-explorer",
    "brave"
]

async def process_app(app_key, desktop, patches):
    config = APPS_CONFIG[app_key]
    logger.info(f"\n📦 PROCESSING: {config['name'].upper()}")

    selected_version = config.get("force_version")

    if not selected_version:
        listing = await get_latest_listing(config["name"])
        if listing and listing.get("version"):
            selected_version = listing["version"]
        else:
            raise Exception("Uygun bir sürüm numarası belirlenemedi.")

    force_build = config.get("force_build")
    apk_path = await download_apk(selected_version, config["name"], force_build)

    extra_args = []
    if config.get("exclude"):
        for p in config["exclude"]:
            extra_args.append(f'--disable "{p}"')
    if config.get("enable"):
        for p in config["enable"]:
            extra_args.append(f'--enable "{p}"')
    extra_args_str = " ".join(extra_args)

    patched_apk = patch_apk(desktop, patches, apk_path, extra_args_str, config["arch"])

    if not patched_apk or not Path(patched_apk).exists():
        return None

    app_display_name = DISPLAY_NAMES.get(config["name"], config["name"])
    final_name = f"{app_display_name}-{selected_version}.apk"
    final_path = Path(final_name)

    shutil.copyfile(patched_apk, final_path)

    return {
        "app_name": config["name"],
        "display_name": app_display_name,
        "icon": config["icon"],
        "patch_source": config["patch_source"],
        "name": final_name,
        "path": str(final_path),
        "version": selected_version
    }

async def main():
    logger.info("Starting patching process...")

    desktop_obj = await asyncio.to_thread(
        download_latest_github_asset,
        owner="MorpheApp",
        repo="morphe-desktop",
        match_func=lambda n: "desktop" in n and n.endswith(".jar")
    )
    desktop = desktop_obj["name"]

    target_app = os.environ.get("TARGET_APP", "all")
    apps_to_process = PROCESS_ORDER if target_app == "all" else [target_app]

    patch_sources_needed = set()
    for app_key in apps_to_process:
        if app_key in APPS_CONFIG:
            patch_sources_needed.add(APPS_CONFIG[app_key]["patch_source"])

    patches_pool = {}
    notes = {}

    if "morphe" in patch_sources_needed:
        mpp = await asyncio.to_thread(
            download_latest_github_asset,
            owner="MorpheApp",
            repo="morphe-patches",
            prerelease=True,
            match_func=lambda n: n.endswith(".mpp")
        )
        patches_pool["morphe"] = mpp["name"]
        notes["morphe"] = f"\n<details>\n<summary>🟢 <b>Morphe Release Notes ({mpp['tag']})</b></summary>\n<br>\n\n{mpp['body']}\n\n</details>\n"

    if "piko" in patch_sources_needed:
        mpp = await asyncio.to_thread(
            download_latest_github_asset,
            owner="crimera",
            repo="piko",
            prerelease=True,
            match_func=lambda n: n.endswith(".mpp")
        )
        patches_pool["piko"] = mpp["name"]
        notes["piko"] = f"\n<details>\n<summary>✖️ <b>Piko Release Notes ({mpp['tag']})</b></summary>\n<br>\n\n{mpp['body']}\n\n</details>\n"

    if "hoodles" in patch_sources_needed:
        mpp = await asyncio.to_thread(
            download_latest_github_asset,
            owner="hoo-dles",
            repo="morphe-patches",
            prerelease=True,
            match_func=lambda n: n.endswith(".mpp")
        )
        patches_pool["hoodles"] = mpp["name"]
        notes["hoodles"] = f"\n<details>\n<summary>🍃 <b>hoo-dles Release Notes ({mpp['tag']})</b></summary>\n<br>\n\n{mpp['body']}\n\n</details>\n"

    if "adobo" in patch_sources_needed:
        mpp = await asyncio.to_thread(
            download_latest_github_asset,
            owner="jkennethcarino",
            repo="adobo",
            prerelease=True,
            match_func=lambda n: n.endswith(".mpp")
        )
        patches_pool["adobo"] = mpp["name"]
        notes["adobo"] = f"\n<details>\n<summary>🥘 <b>Adobo Release Notes ({mpp['tag']})</b></summary>\n<br>\n\n{mpp['body']}\n\n</details>\n"

    if "rushi" in patch_sources_needed:
        mpp = await asyncio.to_thread(
            download_latest_github_asset,
            owner="rushiranpise",
            repo="morphe-patches",
            prerelease=True,
            match_func=lambda n: n.endswith(".mpp")
        )
        patches_pool["rushi"] = mpp["name"]
        notes["rushi"] = f"\n<details>\n<summary>⚡ <b>Rushiranpise Release Notes ({mpp['tag']})</b></summary>\n<br>\n\n{mpp['body']}\n\n</details>\n"

    if "bufferk" in patch_sources_needed:
        mpp = await asyncio.to_thread(
            download_latest_github_asset,
            owner="bufferk",
            repo="morphe-patches",
            prerelease=True,
            match_func=lambda n: n.endswith(".mpp")
        )
        patches_pool["bufferk"] = mpp["name"]
        notes["bufferk"] = f"\n<details>\n<summary>🟣 <b>Bufferk Release Notes ({mpp['tag']})</b></summary>\n<br>\n\n{mpp['body']}\n\n</details>\n"

    patched_apks = []

    for app_key in apps_to_process:
        try:
            source = APPS_CONFIG[app_key]["patch_source"]
            patches_file = patches_pool.get(source)
            if not patches_file:
                logger.error(f"❌ Patch source {source} not available for {app_key}")
                continue
            result = await process_app(app_key, desktop, patches_file)
            if result:
                patched_apks.append(result)
        except Exception as e:
            logger.error(f"❌ {app_key.upper()} failed, skipping: {str(e)}")

    if patched_apks:
        date = datetime.now()
        tag_date_str = date.strftime("%Y-%m-%d-%H-%M-%S")
        release_tag = f"build-{tag_date_str}"
        release_name = f"Patched APKs · {date.strftime('%d %B %Y')}"

        release_body = "### 📦 Latest Patched APKs\n\n"
        for apk in patched_apks:
            release_body += f"* <img src=\"{apk['icon']}\" width=\"16\" height=\"16\"> **{apk['display_name']}**\n"

        release_body += "\n---\n\n"

        for source in patch_sources_needed:
            if source in notes:
                release_body += notes[source]

        logger.info(f"\n📢 Creating New Release: {release_tag}")
        release = ensure_release(release_tag, release_name, release_body)

        microg_uploaded = False
        for apk in patched_apks:
            upload_patched_apk(release, apk["path"])
            if not microg_uploaded and (apk["app_name"] in ("youtube", "youtube-music")):
                upload_microg_once(release)
                microg_uploaded = True

        logger.info("\n🎉 All apps successfully published under one release!")
    else:
        logger.error("No patched APKs to upload.")

if __name__ == "__main__":
    asyncio.run(main())
