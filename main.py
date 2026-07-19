#!/usr/bin/env python3
"""
Morphe APK Patcher – Python edition
"""

import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from lib.github   import download_latest_github_asset
from lib.apkmirror import download_apk as apkmirror_download, get_latest_listing, APP_SITES
from lib.patcher   import patch_apk
from lib.release   import ensure_release, upload_patched_apk, upload_microg_once
from lib.versions  import extract_versions, pick_latest_version

# ── Display names ──────────────────────────────────────────────────────────────
DISPLAY_NAMES = {
    "youtube":          "YouTube",
    "youtube-music":    "YT.Music",
    "reddit":           "Reddit",
    "twitter":          "Twitter",
    "instagram":        "Instagram",
    "github":           "GitHub",
    "niagara-launcher": "Niagara Launcher",
    "pydroid3":         "PyDroid3",
    "smart-launcher":   "Smart Launcher",
    "wps-office":       "WPS Office",
    "gboard":           "Gboard",
    "speedtest":        "Speedtest",
    "solid-explorer":   "Solid Explorer",
    "brave":            "Brave",
}

# ── Apps fetched from APKMirror ────────────────────────────────────────────────
# (all apps are now on APKMirror; githubdl is no longer used)
# Source of truth is apkmirror.APP_SITES, so this can never drift out of sync
# with the apps apkmirror.py actually knows how to download.
APKMIRROR_APPS = set(APP_SITES.keys())

# ── App configurations ─────────────────────────────────────────────────────────
APPS_CONFIG = {
    "youtube": {
        "pkg":         "com.google.android.youtube",
        "patchSource": "morphe",
        "arch":        "arm64-v8a",
        "icon":        "https://cdn.simpleicons.org/youtube/FF0000",
        "exclude":     [],
        "enable":      [],
    },
    "youtube-music": {
        "pkg":         "com.google.android.apps.youtube.music",
        "patchSource": "morphe",
        "arch":        "arm64-v8a",
        "icon":        "https://cdn.simpleicons.org/youtubemusic/FF0000",
        "exclude":     [],
        "enable":      [],
    },
    "reddit": {
        "pkg":         "com.reddit.frontpage",
        "patchSource": "morphe",
        "arch":        "arm64-v8a",
        "icon":        "https://cdn.simpleicons.org/reddit/FF4500",
        "exclude":     [],
        "enable":      [],
    },
    "twitter": {
        "pkg":         "com.twitter.android",
        "patchSource": "piko",
        "arch":        "arm64-v8a",
        "icon":        "https://cdn.simpleicons.org/x/000000",
        "exclude":     ["Dynamic color"],
        "enable":      ["Bring back twitter", "Disunify xchat system", "Export all activities"],
    },
    "instagram": {
        "pkg":          "com.instagram.android",
        "patchSource":  "piko",
        "arch":         "arm64-v8a",
        "icon":         "https://cdn.simpleicons.org/instagram/E4405F",
        "exclude":      [],
        "enable":       [],
        "forceVersion": "435.0.0.37.76",
        "forceBuild":   "384109456",
    },
    "github": {
        "pkg":         "com.github.android",
        "patchSource": "hoodles",
        "arch":        "arm64-v8a",
        "icon":        "https://cdn.simpleicons.org/github/ffffff",
        "exclude":     [],
        "enable":      [],
    },
    "niagara-launcher": {
        "pkg":          "bitpit.launcher",
        "patchSource":  "hoodles",
        "arch":         "arm64-v8a",
        "icon":         "https://www.google.com/s2/favicons?sz=128&domain=niagaralauncher.app",
        "exclude":      [],
        "enable":       [],
        "forceVersion": "1.16.8",
    },
    "pydroid3": {
        "pkg":         "ru.iiec.pydroid3",
        "patchSource": "hoodles",
        "arch":        "arm64-v8a",
        "icon":        "https://www.google.com/s2/favicons?sz=128&domain=pydroid3.com",
        "exclude":     [],
        "enable":      [],
    },
    "smart-launcher": {
        "pkg":         "ginlemon.flowerfree",
        "patchSource": "hoodles",
        "arch":        "arm64-v8a",
        "icon":        "https://www.google.com/s2/favicons?sz=128&domain=smartlauncher.net",
        "exclude":     [],
        "enable":      [],
    },
    "wps-office": {
        "pkg":         "cn.wps.moffice_eng",
        "patchSource": "hoodles",
        "arch":        "arm64-v8a",
        "icon":        "https://www.google.com/s2/favicons?sz=128&domain=wps.com",
        "exclude":     [],
        "enable":      [],
    },
    "gboard": {
        "pkg":         "com.google.android.inputmethod.latin",
        "patchSource": "adobo",
        "arch":        "arm64-v8a",
        "icon":        "https://cdn.simpleicons.org/google/4285F4",
        "exclude":     [],
        "enable":      [
            "Enable voice typing in incognito",
            "Enable key shape selection",
            "Enable clipboard in incognito",
            "Enable access points menu redesign",
            "Enable Undo feature",
            "Enable OCR feature",
            "Always-incognito mode",
        ],
    },
    "speedtest": {
        "pkg":          "org.zwanoo.android.speedtest",
        "patchSource":  "rushi",
        "arch":         "arm64-v8a",
        "icon":         "https://www.google.com/s2/favicons?sz=128&domain=speedtest.net",
        "exclude":      [],
        "enable":       [],
        "forceVersion": "7.0.7",
    },
    "solid-explorer": {
        "pkg":         "pl.solidexplorer2",
        "patchSource": "rushi",
        "arch":        "arm64-v8a",
        "icon":        "https://www.google.com/s2/favicons?sz=128&domain=solidexplorer.com",
        "exclude":     [],
        "enable":      [],
    },
    "brave": {
        "pkg":         "com.brave.browser",
        "patchSource": "bufferk",
        "arch":        "arm64-v8a",
        "icon":        "https://cdn.simpleicons.org/brave/FB542B",
        "exclude":     [],
        "enable":      [],
    },
}

PROCESS_ORDER = [
    "youtube", "youtube-music", "reddit", "twitter",
    "instagram", "github", "niagara-launcher", "pydroid3",
    "smart-launcher", "wps-office", "gboard",
    "speedtest", "solid-explorer", "brave",
]


# ── Patch source → GitHub repo mapping ────────────────────────────────────────
PATCH_SOURCES = {
    "morphe":  {"owner": "MorpheApp",      "repo": "morphe-patches",  "emoji": "🟢", "label": "Morphe"},
    "piko":    {"owner": "crimera",        "repo": "piko",            "emoji": "✖️",  "label": "Piko"},
    "hoodles": {"owner": "hoo-dles",       "repo": "morphe-patches",  "emoji": "🍃", "label": "hoo-dles"},
    "adobo":   {"owner": "jkennethcarino", "repo": "adobo",           "emoji": "🥘", "label": "Adobo"},
    "rushi":   {"owner": "rushiranpise",   "repo": "morphe-patches",  "emoji": "⚡", "label": "Rushiranpise"},
    "bufferk": {"owner": "bufferk",        "repo": "morphe-patches",  "emoji": "🟣", "label": "Bufferk"},
}


def _resolve_version(app_key: str, config: dict, desktop: str, patches: str) -> str:
    """Return the version string to use for this app."""
    # 1. Forced version
    if config.get("forceVersion"):
        return config["forceVersion"]

    # 2. Ask morphe-desktop
    try:
        result = subprocess.run(
            ["java", "-jar", desktop, "list-versions",
             "-f", config["pkg"],
             "--patches", patches,
             "--include-experimental"],
            capture_output=True, text=True, timeout=120,
        )
        versions = extract_versions(result.stdout)
        if versions:
            picked = pick_latest_version(versions)
            if picked:
                return picked
    except Exception as e:
        print(f"  ⚠️  list-versions failed: {e}")

    # 3. Query APKMirror listing
    if app_key in APKMIRROR_APPS:
        listing = get_latest_listing(app_key)
        if listing and listing.get("version"):
            return listing["version"]

    # 4. Generic fallback
    return "latest"


def process_app(app_key: str, desktop: str, patches_pool: dict) -> dict | None:
    config  = APPS_CONFIG[app_key]
    display = DISPLAY_NAMES.get(app_key, app_key)
    patches = patches_pool[config["patchSource"]]

    print(f"\n{'='*60}")
    print(f"📦 PROCESSING: {app_key.upper()}")
    print(f"{'='*60}")

    version = _resolve_version(app_key, config, desktop, patches)
    print(f"  📌 Version: {version}")

    # Download APK
    force_build = config.get("forceBuild")
    apk_path = apkmirror_download(version, app_key, force_build)

    # Build extra patch flags
    extra_args: list[str] = []
    for p in config.get("exclude", []):
        extra_args += ["--disable", p]
    for p in config.get("enable", []):
        extra_args += ["--enable", p]

    patched = patch_apk(desktop, patches, apk_path, extra_args or None, config["arch"])

    if not Path(patched).exists():
        return None

    final_name = f"{display}-{version}.apk"
    final_path = Path.cwd() / final_name
    shutil.copy2(patched, final_path)

    return {
        "appName":     app_key,
        "displayName": display,
        "icon":        config["icon"],
        "patchSource": config["patchSource"],
        "name":        final_name,
        "path":        str(final_path),
        "version":     version,
    }


def main():
    # ── Download morphe-desktop ────────────────────────────────────────────────
    desktop_info = download_latest_github_asset(
        owner="MorpheApp",
        repo="morphe-desktop",
        match_fn=lambda n: "desktop" in n and n.endswith(".jar"),
    )
    desktop = desktop_info["name"]

    # ── Determine which apps to process ───────────────────────────────────────
    target = os.environ.get("TARGET_APP", "all")
    apps   = PROCESS_ORDER if target == "all" else [target]

    # ── Download needed patch bundles ─────────────────────────────────────────
    # Order-preserving de-dup (not a set) so release notes always render in
    # the same order across runs instead of shuffling arbitrarily.
    needed_sources: list[str] = []
    for k in apps:
        src = APPS_CONFIG[k]["patchSource"]
        if src not in needed_sources:
            needed_sources.append(src)
    patches_pool: dict[str, str]     = {}
    release_notes: dict[str, str]    = {}

    for src in needed_sources:
        info = PATCH_SOURCES[src]
        mpp  = download_latest_github_asset(
            owner=info["owner"],
            repo=info["repo"],
            prerelease=True,
            match_fn=lambda n: n.endswith(".mpp"),
        )
        patches_pool[src]  = mpp["name"]
        release_notes[src] = (
            f"\n<details>\n"
            f"<summary>{info['emoji']} <b>{info['label']} Release Notes ({mpp['tag']})</b></summary>\n"
            f"<br>\n\n{mpp['body']}\n\n</details>\n"
        )

    # ── Process each app ──────────────────────────────────────────────────────
    patched_list: list[dict] = []
    for app_key in apps:
        try:
            result = process_app(app_key, desktop, patches_pool)
            if result:
                patched_list.append(result)
        except Exception as err:
            print(f"\n  ❌ {app_key.upper()} failed, skipping: {err}")

    if not patched_list:
        print("\n⚠️  No apps were successfully patched.")
        return

    # ── Create GitHub release ──────────────────────────────────────────────────
    now       = datetime.now(timezone.utc)
    tag       = "build-" + now.strftime("%Y-%m-%dT%H-%M-%S")
    rel_name  = "Patched APKs · " + now.strftime("%B %-d, %Y")

    body = "### 📦 Latest Patched APKs\n\n"
    for apk in patched_list:
        body += f'* <img src="{apk["icon"]}" width="16" height="16"> **{apk["displayName"]}**\n'
    body += "\n---\n"
    for src in needed_sources:
        body += release_notes.get(src, "")

    print(f"\n📢 Creating release: {tag}")
    release = ensure_release(tag, rel_name, body)

    microg_uploaded = False
    for apk in patched_list:
        upload_patched_apk(release, apk["path"])
        if not microg_uploaded and apk["appName"] in ("youtube", "youtube-music"):
            upload_microg_once(release)
            microg_uploaded = True

    print("\n🎉 All apps published successfully!")


if __name__ == "__main__":
    main()
