import asyncio
import os
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path

from lib.github import download_latest_github_asset
from lib.versions import extract_youtube_versions, pick_latest_version
from lib.patcher import patch_apk
from lib.release import ensure_release, upload_patched_apk, upload_microg_once
from lib import apkmirror
from lib import githubdl

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
    "nova-launcher": "Nova Launcher",
}

APKMIRROR_APPS = [
    "youtube", "youtube-music", "reddit", "twitter",
    "github", "niagara-launcher", "smart-launcher",
    "solid-explorer", "pydroid3", "gboard", "brave", "nova-launcher",
]

APPS_CONFIG = {
    "youtube": {
        "pkg": "com.google.android.youtube", "name": "youtube", "patch_source": "morphe",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/youtube/FF0000", "exclude": [],
    },
    "youtube-music": {
        "pkg": "com.google.android.apps.youtube.music", "name": "youtube-music", "patch_source": "morphe",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/youtubemusic/FF0000", "exclude": [],
    },
    "reddit": {
        "pkg": "com.reddit.frontpage", "name": "reddit", "patch_source": "morphe",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/reddit/FF4500", "exclude": [],
    },
    "twitter": {
        "pkg": "com.twitter.android", "name": "twitter", "patch_source": "piko",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/x/000000",
        "exclude": ["Dynamic color"],
        "enable": ["Bring back twitter", "Disunify xchat system", "Export all activities"],
    },
    "instagram": {
        "pkg": "com.instagram.android", "name": "instagram", "patch_source": "piko",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/instagram/E4405F",
        "exclude": [], "enable": [],
        "force_version": "435.0.0.37.76", "force_build": "384109456",
    },
    "github": {
        "pkg": "com.github.android", "name": "github", "patch_source": "hoo-dles",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/github/ffffff", "exclude": [],
    },
    "niagara-launcher": {
        "pkg": "bitpit.launcher", "name": "niagara-launcher", "patch_source": "hoo-dles",
        "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=niagaralauncher.app",
        "exclude": [], "force_version": "1.16.8",
    },
    "pydroid3": {
        "pkg": "ru.iiec.pydroid3", "name": "pydroid3", "patch_source": "hoo-dles",
        "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=pydroid3.com", "exclude": [],
    },
    "smart-launcher": {
        "pkg": "ginlemon.flowerfree", "name": "smart-launcher", "patch_source": "hoo-dles",
        "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=smartlauncher.net", "exclude": [],
    },
    "wps-office": {
        "pkg": "cn.wps.moffice_eng", "name": "wps-office", "patch_source": "hoo-dles",
        "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=wps.com", "exclude": [],
    },
    "gboard": {
        "pkg": "com.google.android.inputmethod.latin", "name": "gboard", "patch_source": "adobo",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/google/4285F4",
        "exclude": [],
        "enable": [
            "Enable voice typing in incognito", "Enable key shape selection",
            "Enable clipboard in incognito", "Enable access points menu redesign",
            "Enable Undo feature", "Enable OCR feature", "Always-incognito mode",
        ],
    },
    "speedtest": {
        "pkg": "org.zwanoo.android.speedtest", "name": "speedtest", "patch_source": "rushi",
        "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=speedtest.net",
        "exclude": [], "force_version": "7.0.7",
    },
    "solid-explorer": {
        "pkg": "pl.solidexplorer2", "name": "solid-explorer", "patch_source": "rushi",
        "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=solidexplorer.com", "exclude": [],
    },
    "brave": {
        "pkg": "com.brave.browser", "name": "brave", "patch_source": "bufferk",
        "arch": "arm64-v8a", "icon": "https://cdn.simpleicons.org/brave/FB542B", "exclude": [],
    },
    "nova-launcher": {
        "pkg": "com.teslacoilsw.launcher", "name": "nova-launcher", "patch_source": "hoo-dles",
        "arch": "arm64-v8a", "icon": "https://www.google.com/s2/favicons?sz=128&domain=novalauncher.com", "exclude": [],
    },
}

PROCESS_ORDER = [
    "youtube", "youtube-music", "reddit", "twitter", "instagram",
    "github", "niagara-launcher", "pydroid3", "smart-launcher",
    "wps-office", "gboard", "speedtest", "solid-explorer", "brave", "nova-launcher",
]

PATCH_SOURCES = {
    "morphe": ("MorpheApp", "morphe-patches", "🟢 Morphe"),
    "piko": ("crimera", "piko", "✖️ Piko"),
    "hoo-dles": ("hoo-dles", "morphe-patches", "🍃 hoo-dles"),
    "adobo": ("jkennethcarino", "adobo", "🥘 Adobo"),
    "rushi": ("rushiranpise", "morphe-patches", "⚡ Rushiranpise"),
    "bufferk": ("bufferk", "morphe-patches", "🟣 Bufferk"),
}


async def process_app(app_key: str, desktop: str, patches: str) -> dict | None:
    config = APPS_CONFIG[app_key]
    print(f"\n📦 PROCESSING: {config['name'].upper()}")

    is_apkmirror_app = config["name"] in APKMIRROR_APPS

    selected_version = config.get("force_version")

    if not selected_version:
        try:
            result = subprocess.run(
                ["java", "-jar", desktop, "list-versions", "-f", config["pkg"],
                 "--patches", patches, "--include-experimental"],
                capture_output=True, text=True,
            )
            output = (result.stdout or "") + (result.stderr or "")
            versions = extract_youtube_versions(output)
            if versions:
                selected_version = pick_latest_version(versions)
        except Exception as e:
            print(f"⚠️ Sürüm listesi alınamadı: {e}")

    if not selected_version:
        if not is_apkmirror_app:
            selected_version = "latest"
        else:
            latest = await apkmirror.get_latest_listing(config["name"])
            if latest and latest.get("version"):
                selected_version = latest["version"]

    if not selected_version:
        raise RuntimeError("Uygun bir sürüm numarası belirlenemedi.")

    if is_apkmirror_app:
        apk_path = await apkmirror.download_apk(selected_version, config["name"], config.get("force_build"))
    else:
        apk_path = await githubdl.download_apk(selected_version, config["name"], config.get("force_build"))

    patched_apk = patch_apk(
        desktop, patches, apk_path,
        exclude=config.get("exclude"),
        enable=config.get("enable"),
        arch=config["arch"],
    )

    if not Path(patched_apk).exists():
        return None

    display_name = DISPLAY_NAMES.get(config["name"], config["name"])
    final_name = f"{display_name}-{selected_version}.apk"
    final_path = Path.cwd() / final_name

    shutil.copyfile(patched_apk, final_path)

    return {
        "app_name": config["name"],
        "display_name": display_name,
        "icon": config["icon"],
        "patch_source": config["patch_source"],
        "name": final_name,
        "path": str(final_path),
        "version": selected_version,
    }


async def main():
    try:
        desktop_obj = await download_latest_github_asset(
            owner="MorpheApp", repo="morphe-desktop",
            match=lambda n: "desktop" in n and n.endswith(".jar"),
        )
        desktop = desktop_obj["name"]

        target_app = os.environ.get("TARGET_APP", "all")
        apps_to_process = PROCESS_ORDER if target_app == "all" else [target_app]

        if any(APPS_CONFIG[k]["name"] in APKMIRROR_APPS for k in apps_to_process):
            await apkmirror.warmup_browser()

        patches_pool: dict[str, str | None] = {k: None for k in PATCH_SOURCES}
        notes: dict[str, str] = {k: "" for k in PATCH_SOURCES}
        needed: dict[str, bool] = {}

        for key, (owner, repo, label) in PATCH_SOURCES.items():
            needed[key] = any(APPS_CONFIG[k]["patch_source"] == key for k in apps_to_process)
            if needed[key]:
                asset = await download_latest_github_asset(
                    owner=owner, repo=repo, prerelease=True,
                    match=lambda n: n.endswith(".mpp"),
                )
                patches_pool[key] = asset["name"]
                notes[key] = (
                    f"\n<details>\n<summary>{label} Release Notes ({asset['tag']})</summary>\n<br>\n\n"
                    f"{asset['body']}\n\n</details>\n"
                )

        patched_apks_list = []

        for app_key in apps_to_process:
            try:
                result = await process_app(app_key, desktop, patches_pool[APPS_CONFIG[app_key]["patch_source"]])
                if result:
                    patched_apks_list.append(result)
            except Exception as err:
                print(f"❌ {app_key.upper()} failed, skipping: {err}")

        if patched_apks_list:
            date = datetime.now(timezone.utc)
            tag_date_str = date.strftime("%Y-%m-%dT%H-%M-%S")
            release_tag = f"build-{tag_date_str}"
            release_name = f"Patched APKs · {date.day} {date.strftime('%B %Y')}"

            body = "### 📦 Latest Patched APKs\n\n"
            for apk in patched_apks_list:
                body += f'* <img src="{apk["icon"]}" width="16" height="16"> **{apk["display_name"]}**\n'
            body += "\n---\n\n"

            for key in PATCH_SOURCES:
                if needed[key] and notes[key]:
                    body += notes[key]

            print(f"\n📢 Creating New Release: {release_tag}")
            release = await ensure_release(release_tag, release_name, body)

            microg_uploaded = False
            for apk in patched_apks_list:
                await upload_patched_apk(release, apk["path"])
                if not microg_uploaded and apk["app_name"] in ("youtube", "youtube-music"):
                    await upload_microg_once(release)
                    microg_uploaded = True

            print("\n🎉 All apps successfully published under one release!")

    except Exception as err:
        print("❌ Fatal error:", err)
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
