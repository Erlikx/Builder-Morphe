import asyncio
import os

from lib.github import download_latest_github_asset
from lib.release import get_release_by_tag, update_release_body, delete_other_releases
from lib.config import APPS_CONFIG, DISPLAY_NAMES, PATCH_SOURCES

NAME_TO_KEY = {v: k for k, v in DISPLAY_NAMES.items()}


def match_asset(file_name: str):
    if not file_name.endswith(".apk"):
        return None
    if file_name.startswith("MicroG"):
        return None

    base = file_name[:-4]
    for display_name, app_key in NAME_TO_KEY.items():
        prefix = display_name + "-"
        if base.startswith(prefix):
            return app_key, display_name, base[len(prefix):]

    return None


async def main():
    release_tag = os.environ["RELEASE_TAG"]
    release = await get_release_by_tag(release_tag)

    assets = release.get("assets", [])
    successful = []

    for asset in assets:
        matched = match_asset(asset["name"])
        if matched:
            successful.append(matched)

    if not successful:
        print("No published APKs found, leaving release body as is.")
        return

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

    await update_release_body(release["id"], body)
    print("Release body updated.")

    await delete_other_releases(release["id"])
    print("Old releases deleted.")


if __name__ == "__main__":
    asyncio.run(main())
