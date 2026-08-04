import asyncio
import os
import re

from lib.github import download_latest_github_asset
from lib.release import get_release_by_tag, update_release_body, delete_other_releases
from lib.config import APPS_CONFIG, DISPLAY_NAMES, PATCH_SOURCES

NAME_TO_KEY = {v: k for k, v in DISPLAY_NAMES.items()}


def _normalize(text: str) -> str:
    return re.sub(r"[ ._-]+", "", text).lower()


def match_asset(file_name: str):
    if not file_name.lower().endswith(".apk"):
        return None
    if file_name.lower().startswith("microg"):
        return None

    base = file_name[:-4]

    try:
        last_dash = base.rindex("-")
    except ValueError:
        return None

    name_part = base[:last_dash]
    version_part = base[last_dash + 1:]

    normalized_name_part = _normalize(name_part)

    for display_name, app_key in NAME_TO_KEY.items():
        if _normalize(display_name) == normalized_name_part:
            return app_key, display_name, version_part

    return None


async def main():
    release_tag = os.environ["RELEASE_TAG"]
    print(f"Fetching release: {release_tag}")
    release = await get_release_by_tag(release_tag)
    print(f"Release id={release['id']}")

    assets = release.get("assets", [])
    print(f"Found {len(assets)} asset(s) on the release:")
    for asset in assets:
        print(f"  - {asset['name']}")

    successful = []
    for asset in assets:
        matched = match_asset(asset["name"])
        if matched:
            successful.append(matched)
        else:
            print(f"Could not match asset to a known app: {asset['name']}")

    print(f"Matched {len(successful)} app asset(s).")

    if successful:
        body = "### Latest Patched APKs\n\n"
        for app_key, display_name, version in successful:
            icon = APPS_CONFIG[app_key]["icon"]
            body += f'* <img src="{icon}" width="16" height="16"> **{display_name}** - `{version}`\n'

        body += "\n---\n\n"

        used_sources = sorted({APPS_CONFIG[app_key]["patch_source"] for app_key, _, _ in successful})

        for key in used_sources:
            if key not in PATCH_SOURCES:
                continue
            owner, repo, label = PATCH_SOURCES[key]
            try:
                asset = await download_latest_github_asset(
                    owner=owner, repo=repo, prerelease=True,
                    match=lambda n: n.endswith(".mpp"),
                )
                body += (
                    f"\n<details>\n<summary>{label} Release Notes ({asset['tag']})</summary>\n<br>\n\n"
                    f"{asset['body']}\n\n</details>\n"
                )
            except Exception as e:
                print(f"Could not fetch release notes for {label}: {e}")

        try:
            await update_release_body(release["id"], body)
            print("Release body updated.")
        except Exception as e:
            print(f"Failed to update release body: {e}")
    else:
        print("No published APKs matched, leaving release body as is.")

    try:
        await delete_other_releases(release["id"])
        print("Old releases deleted.")
    except Exception as e:
        print(f"Failed to delete old releases: {e}")


if __name__ == "__main__":
    asyncio.run(main())
