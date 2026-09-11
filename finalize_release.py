import asyncio
from pathlib import Path

from core import log, notify
from core.config import APPS_CONFIG, PATCH_SOURCES, PROCESS_ORDER, get_release_naming, patch_sources_for
from core.patch_tools import download_latest_github_asset
from core.release import create_new_release, delete_other_releases, upload_microg_once, upload_patched_apk
from core.settings import settings


def _build_asset_candidates() -> list[tuple[str, str, str | None]]:
    candidates = []
    for app_key in APPS_CONFIG:
        display_name, tag = get_release_naming(app_key)
        candidates.append((app_key, display_name, tag))
    candidates.sort(key=lambda c: -len(c[1]))
    return candidates


_ASSET_CANDIDATES = _build_asset_candidates()


def match_asset(file_name: str):
    if not file_name.lower().endswith(".apk"):
        return None
    if file_name.lower().startswith("microg"):
        return None

    base = file_name[:-4]

    for app_key, display_name, tag in _ASSET_CANDIDATES:
        prefix = display_name + "-"
        if not base.lower().startswith(prefix.lower()):
            continue

        remainder = base[len(prefix) :]

        if tag:
            suffix = f"-{tag}"
            if not remainder.lower().endswith(suffix.lower()):
                continue
            remainder = remainder[: -len(suffix)]

        return app_key, display_name, remainder

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
    if not settings.release_tag or not settings.release_name:
        raise RuntimeError("Missing RELEASE_TAG/RELEASE_NAME (expected to be set by prepare_release.py's output)")
    release_tag = settings.release_tag
    release_name = settings.release_name
    artifacts_dir = settings.artifacts_dir

    log.step(f"Scanning {artifacts_dir} for patched APKs...")
    matched, unmatched = find_patched_apks(artifacts_dir)

    for name in unmatched:
        log.warn(f"Could not match asset to a known app: {name}")

    log.info(f"Matched {len(matched)} app asset(s).")

    succeeded_keys = {apk["app_key"] for apk in matched}
    failed_keys = [key for key in PROCESS_ORDER if key not in succeeded_keys]

    if not matched:
        log.error("No apps patched successfully in this run, skipping release creation.")
        await notify.notify(notify.format_all_failed(release_name, failed_keys))
        return

    body = "### Latest Patched APKs\n\n"
    for apk in matched:
        icon = APPS_CONFIG[apk["app_key"]]["icon"]
        body += f'* <img src="{icon}" width="16" height="16"> **{apk["display_name"]}** - `{apk["version"]}`\n'

    body += "\n---\n\n"

    used_sources: set[str] = set()
    for apk in matched:
        used_sources.update(patch_sources_for(apk["app_key"]))

    for key in sorted(used_sources):
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
            log.warn(f"Could not fetch release notes for {label}: {e}")

    log.step(f"Creating release: {release_tag}")
    release = await create_new_release(release_tag, release_name, body, draft=False)
    log.success(f"Release created: {release['tag_name']} (id={release['id']})")

    for apk in matched:
        await upload_patched_apk(release, apk["path"])

    if any(apk["app_key"] in ("youtube", "youtube-music") for apk in matched):
        await upload_microg_once(release)

    log.success("All apps successfully published under one release!")

    try:
        await delete_other_releases(release["id"])
        log.info("Old releases deleted.")
    except Exception as e:
        log.warn(f"Failed to delete old releases: {e}")

    release_url = release.get("html_url") or (
        f"https://github.com/{settings.github_repository}/releases/tag/{release_tag}"
    )
    await notify.notify(notify.format_summary(release_name, release_url, matched, failed_keys))


if __name__ == "__main__":
    asyncio.run(main())
