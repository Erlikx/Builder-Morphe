import asyncio
import os
import random
import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path

from lib.github import download_latest_github_asset
from lib.versions import extract_youtube_versions, pick_latest_version
from lib.patcher import patch_apk
from lib.release import ensure_release, get_release_by_tag, upload_patched_apk, upload_microg_once
from lib.verify import verify_apk_signature
from lib import apkmirror
from lib import githubdl

from lib.config import (
    DISPLAY_NAMES,
    APKMIRROR_APPS,
    APPS_CONFIG,
    PROCESS_ORDER,
    PATCH_SOURCES,
)


async def process_app(app_key: str, desktop: str, patches: str) -> dict | None:
    config = APPS_CONFIG[app_key]
    print(f"\nPROCESSING: {config['name'].upper()}")

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
            print(f"Could not fetch version list: {e}")

    if not selected_version:
        if not is_apkmirror_app:
            selected_version = "latest"
        else:
            latest = await apkmirror.get_latest_listing(config["name"])
            if latest and latest.get("version"):
                selected_version = latest["version"]

    if not selected_version:
        raise RuntimeError("Could not determine a suitable version number.")

    if is_apkmirror_app:
        apk_path = await apkmirror.download_apk(selected_version, config["name"], config.get("force_build"))
    else:
        apk_path = await githubdl.download_apk(selected_version, config["name"], config.get("force_build"))

    verify_apk_signature(apk_path, config["name"])

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
            prerelease=True,
            match=lambda n: "desktop" in n and n.endswith(".jar"),
        )
        desktop = desktop_obj["name"]

        target_app = os.environ.get("TARGET_APP", "all")
        apps_to_process = PROCESS_ORDER if target_app == "all" else [target_app]

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
        failed_apps = []

        for app_key in apps_to_process:
            try:
                result = await process_app(app_key, desktop, patches_pool[APPS_CONFIG[app_key]["patch_source"]])
                if result:
                    patched_apks_list.append(result)
                else:
                    failed_apps.append(app_key)
            except Exception as err:
                print(f"{app_key.upper()} failed, skipping: {err}")
                failed_apps.append(app_key)

            if APPS_CONFIG[app_key]["name"] in APKMIRROR_APPS and app_key != apps_to_process[-1]:
                print("Closing browser session to get a fresh session for the next app...")
                await apkmirror.close_browser()

                delay = random.uniform(6.0, 14.0)
                print(f"Waiting {delay:.0f}s before the next app (to reduce APKMirror request rate)...")
                await asyncio.sleep(delay)

        if patched_apks_list:
            release_tag_env = os.environ.get("RELEASE_TAG")

            if release_tag_env:
                print(f"\nUsing shared release (matrix job): {release_tag_env}")
                release = await get_release_by_tag(release_tag_env)
            else:
                date = datetime.now(timezone.utc)
                tag_date_str = date.strftime("%Y-%m-%dT%H-%M-%S")
                release_tag = f"build-{tag_date_str}"
                release_name = f"Patched APKs - {date.day} {date.strftime('%B %Y')}"

                body = "### Latest Patched APKs\n\n"
                for apk in patched_apks_list:
                    body += f'* <img src="{apk["icon"]}" width="16" height="16"> **{apk["display_name"]}**\n'
                body += "\n---\n\n"

                for key in PATCH_SOURCES:
                    if needed[key] and notes[key]:
                        body += notes[key]

                print(f"\nCreating new release: {release_tag}")
                release = await ensure_release(release_tag, release_name, body)

            microg_uploaded = False
            for apk in patched_apks_list:
                await upload_patched_apk(release, apk["path"])
                if not microg_uploaded and apk["app_name"] in ("youtube", "youtube-music"):
                    await upload_microg_once(release)
                    microg_uploaded = True

            print("\nAll apps successfully published under one release!")

        if failed_apps:
            print(f"\nFailed app(s): {', '.join(failed_apps)}")
            raise SystemExit(1)

    except SystemExit:
        raise
    except Exception as err:
        print("Fatal error:", err)
        raise SystemExit(1)
    finally:
        await apkmirror.close_browser()


if __name__ == "__main__":
    asyncio.run(main())
