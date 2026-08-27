import asyncio
import os
import random
import shutil
import subprocess
from pathlib import Path

from core import log
from core.apk.patcher import patch_apk
from core.apk.verify import verify_apk_signature
from core.apk.versions import extract_youtube_versions, pick_latest_version
from core.config import (
    APKMIRROR_APPS,
    APPS_CONFIG,
    DISPLAY_NAMES,
    PATCH_SOURCES,
    PROCESS_ORDER,
)
from core.patch_tools import download_latest_github_asset
from core.sources import apkmirror, github_apk

DIST_DIR = Path.cwd() / "dist"


async def process_app(app_key: str, desktop: str, patches: str) -> dict | None:
    config = APPS_CONFIG[app_key]
    log.header(f"PROCESSING: {config['name'].upper()}")

    is_apkmirror_app = config["name"] in APKMIRROR_APPS

    selected_version = config.get("force_version")

    if not selected_version:
        try:
            result = subprocess.run(
                [
                    "java",
                    "-jar",
                    desktop,
                    "list-versions",
                    "-f",
                    config["pkg"],
                    "--patches",
                    patches,
                    "--include-experimental",
                ],
                capture_output=True,
                text=True,
            )
            output = (result.stdout or "") + (result.stderr or "")
            versions = extract_youtube_versions(output)
            if versions:
                selected_version = pick_latest_version(versions)
        except Exception as e:
            log.warn(f"Could not fetch version list: {e}")

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
        apk_path = await github_apk.download_apk(selected_version, config["name"], config.get("force_build"))

    verify_apk_signature(apk_path, config["name"])

    patched_apk = patch_apk(
        desktop,
        patches,
        apk_path,
        exclude=config.get("exclude"),
        enable=config.get("enable"),
        arch=config["arch"],
    )

    if not Path(patched_apk).exists():
        return None

    display_name = DISPLAY_NAMES.get(app_key, config["name"])
    final_name = f"{display_name}-{selected_version}.apk"
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    final_path = DIST_DIR / final_name

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
            owner="MorpheApp",
            repo="morphe-desktop",
            prerelease=True,
            match=lambda n: "desktop" in n and n.endswith(".jar"),
        )
        desktop = desktop_obj["name"]

        target_app = os.environ.get("TARGET_APP", "all")
        apps_to_process = PROCESS_ORDER if target_app == "all" else [target_app]

        patches_pool: dict[str, str | None] = {k: None for k in PATCH_SOURCES}

        for key, (owner, repo, _label) in PATCH_SOURCES.items():
            needed = any(APPS_CONFIG[k]["patch_source"] == key for k in apps_to_process)
            if needed:
                asset = await download_latest_github_asset(
                    owner=owner,
                    repo=repo,
                    prerelease=True,
                    match=lambda n: n.endswith(".mpp"),
                )
                patches_pool[key] = asset["name"]

        patched_apks_list = []
        failed_apps = []

        for app_key in apps_to_process:
            try:
                patch_source = APPS_CONFIG[app_key]["patch_source"]
                patch_file = patches_pool[patch_source]
                if patch_file is None:
                    raise RuntimeError(f"No patch file resolved for source '{patch_source}'")
                result = await process_app(app_key, desktop, patch_file)
                if result:
                    patched_apks_list.append(result)
                    log.success(f"{app_key.upper()} done: {result['name']}")
                else:
                    failed_apps.append(app_key)
            except Exception as err:
                log.error(f"{app_key.upper()} failed, skipping: {err}")
                failed_apps.append(app_key)

            if APPS_CONFIG[app_key]["name"] in APKMIRROR_APPS and app_key != apps_to_process[-1]:
                delay = random.uniform(6.0, 14.0)
                log.wait(f"Waiting {delay:.0f}s before the next app (to reduce APKMirror request rate)...")
                await asyncio.sleep(delay)

        if patched_apks_list:
            names = ", ".join(apk["name"] for apk in patched_apks_list)
            log.saved(f"Patched APK(s) ready in {DIST_DIR}: {names}")
            log.info("These will be picked up as a workflow artifact and published in the finalize job.")

        if failed_apps:
            log.error(f"Failed app(s): {', '.join(failed_apps)}")
            raise SystemExit(1)

    except SystemExit:
        raise
    except Exception as err:
        log.error(f"Fatal error: {err}")
        raise SystemExit(1) from err
    finally:
        await apkmirror.close_browser()


if __name__ == "__main__":
    asyncio.run(main())
