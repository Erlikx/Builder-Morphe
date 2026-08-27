import asyncio
import os
from pathlib import Path

from core import notify
from core.config import APPS_CONFIG, DISPLAY_NAMES, PATCH_SOURCES, PROCESS_ORDER
from core.patch_tools import download_latest_github_asset
from core.release import create_new_release, delete_other_releases, upload_microg_once, upload_patched_apk

NAME_TO_KEY = {v: k for k, v in DISPLAY_NAMES.items()}


def match_asset(file_name: str):
    if not file_name.lower().endswith(".apk"):
        return None
    if file_name.lower().startswith("microg"):
        return None

    base = file_name[:-4]

    for display_name, app_key in sorted(NAME_TO_KEY.items(), key=lambda kv: -len(kv[0])):
        prefix = display_name + "-"
        if base.lower().startswith(prefix.lower()):
            version_part = base[len(prefix) :]
            return app_key, display_name, version_part

    return None


def find_patched_apks(artifacts_dir: Path):
    matched = []
    unmatched = []

    for apk_path in sorted(artifacts_dir.rglob("*.apk")):
        result = match_asset(apk_path.name)
        if result:
            app_key, display_name, version = result
            matched.append(
                {
                    "app_key": app_key,
                    "display_name": display_name,
                    "version": version,
                    "path": str(apk_path),
                    "name": apk_path.name,
                }
            )
        else:
            unmatched.append(apk_path.name)

    return matched, unmatched


async def main():
    release_tag = os.environ["RELEASE_TAG"]
    release_name = os.environ["RELEASE_NAME"]
    artifacts_dir = Path(os.environ.get("ARTIFACTS_DIR", "artifacts"))

    print(f"Scanning {artifacts_dir} for patched APKs...")
    matched, unmatched = find_patched_apks(artifacts_dir)

    for name in unmatched:
        print(f"Could not match asset to a known app: {name}")

    print(f"Matched {len(matched)} app asset(s).")

    succeeded_keys = {apk["app_key"] for apk in matched}
    failed_keys = [key for key in PROCESS_ORDER if key not in succeeded_keys]

    if not matched:
        print("No apps patched successfully in this run, skipping release creation.")
        await notify.notify(notify.format_all_failed(release_name, failed_keys))
        return

    body = "### Latest Patched APKs\n\n"
    for apk in matched:
        icon = APPS_CONFIG[apk["app_key"]]["icon"]
        body += f'* <img src="{icon}" width="16" height="16"> **{apk["display_name"]}** - `{apk["version"]}`\n'

    body += "\n---\n\n"

    used_sources = sorted({APPS_CONFIG[apk["app_key"]]["patch_source"] for apk in matched})

    for key in used_sources:
        if key not in PATCH_SOURCES:
            continue
        owner, repo, label = PATCH_SOURCES[key]
        try:
            asset = await download_latest_github_asset(
                owner=owner,
                repo=repo,
                prerelease=True,
                match=lambda n: n.endswith(".mpp"),
            )
            body += (
                f"\n<details>\n<summary>{label} Release Notes ({asset['tag']})</summary>\n<br>\n\n"
                f"{asset['body']}\n\n</details>\n"
            )
        except Exception as e:
            print(f"Could not fetch release notes for {label}: {e}")

    print(f"\nCreating release: {release_tag}")
    release = await create_new_release(release_tag, release_name, body, draft=False)
    print(f"Release created: {release['tag_name']} (id={release['id']})")

    for apk in matched:
        await upload_patched_apk(release, apk["path"])

    if any(apk["app_key"] in ("youtube", "youtube-music") for apk in matched):
        await upload_microg_once(release)

    print("\nAll apps successfully published under one release!")

    try:
        await delete_other_releases(release["id"])
        print("Old releases deleted.")
    except Exception as e:
        print(f"Failed to delete old releases: {e}")

    release_url = release.get("html_url") or (
        f"https://github.com/{os.environ.get('GITHUB_REPOSITORY', '')}/releases/tag/{release_tag}"
    )
    await notify.notify(notify.format_summary(release_name, release_url, matched, failed_keys))


if __name__ == "__main__":
    asyncio.run(main())
