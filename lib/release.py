import os
from pathlib import Path

import httpx

from .github import download_latest_github_asset
from . import log

TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO = os.environ.get("GITHUB_REPOSITORY", "")

HEADERS = {
    "User-Agent": "python",
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}


def _assert_configured():
    if not TOKEN:
        raise RuntimeError("Missing GITHUB_TOKEN")
    if not REPO:
        raise RuntimeError("Missing GITHUB_REPOSITORY")


async def create_new_release(tag: str, release_name: str, release_body: str = "", draft: bool = False) -> dict:
    _assert_configured()
    log.step(f"Creating new release: {tag}")

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            f"https://api.github.com/repos/{REPO}/releases",
            headers=HEADERS,
            json={
                "tag_name": tag,
                "name": release_name,
                "body": release_body,
                "draft": draft,
                "prerelease": False,
                "make_latest": "false" if draft else "true",
            },
        )
        data = res.json()

    if "id" not in data:
        raise RuntimeError(f"Failed to create release: {data}")

    return data


async def list_releases() -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            f"https://api.github.com/repos/{REPO}/releases",
            headers=HEADERS,
            params={"per_page": 100},
        )
        data = res.json()

    if not isinstance(data, list):
        raise RuntimeError(f"Failed to list releases: {data}")

    return data


async def delete_release(release_id: int) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        await client.delete(
            f"https://api.github.com/repos/{REPO}/releases/{release_id}",
            headers=HEADERS,
        )


async def delete_tag(tag: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        await client.delete(
            f"https://api.github.com/repos/{REPO}/git/refs/tags/{tag}",
            headers=HEADERS,
        )


async def delete_other_releases(keep_release_id: int) -> None:
    releases = await list_releases()

    for release in releases:
        if release["id"] == keep_release_id:
            continue
        log.warn(f"Deleting old release: {release.get('tag_name')}")
        await delete_release(release["id"])
        await delete_tag(release["tag_name"])


async def update_release_body(release_id: int, body: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.patch(
            f"https://api.github.com/repos/{REPO}/releases/{release_id}",
            headers=HEADERS,
            json={"body": body},
        )
        return res.json()


async def get_assets(release_id: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.get(
            f"https://api.github.com/repos/{REPO}/releases/{release_id}/assets",
            headers=HEADERS,
        )
        return res.json()


async def delete_asset(asset_id: int):
    async with httpx.AsyncClient(timeout=30) as client:
        await client.delete(
            f"https://api.github.com/repos/{REPO}/releases/assets/{asset_id}",
            headers=HEADERS,
        )


async def _upload(upload_url: str, file_path: str) -> dict:
    file_name = Path(file_path).name
    data = Path(file_path).read_bytes()

    url = upload_url.replace("{?name,label}", "") + f"?name={file_name}"

    async with httpx.AsyncClient(timeout=None) as client:
        res = await client.post(
            url,
            headers={
                **HEADERS,
                "Content-Type": "application/vnd.android.package-archive",
            },
            content=data,
        )
        return res.json()


async def upload_with_replace(release: dict, file_path: str):
    file_name = Path(file_path).name

    assets = await get_assets(release["id"])
    existing = next((a for a in assets if a["name"] == file_name), None)

    if existing:
        log.warn(f"Replacing existing asset: {file_name}")
        await delete_asset(existing["id"])

    log.download(f"Uploading: {file_name}")
    return await _upload(release["upload_url"], file_path)


async def upload_patched_apk(release: dict, apk_path: str):
    _assert_configured()
    await upload_with_replace(release, apk_path)


async def upload_microg_once(release: dict):
    _assert_configured()

    log.step("Fetching MicroG...")
    microg_result = await download_latest_github_asset(
        owner="MorpheApp",
        repo="MicroG-RE",
        match=lambda n: n.endswith(".apk"),
    )

    original_path = Path.cwd() / microg_result["name"]
    new_path = Path.cwd() / "MicroG.apk"

    if original_path.exists() and original_path != new_path:
        original_path.rename(new_path)

    assets = await get_assets(release["id"])
    already_uploaded = next((a for a in assets if a["name"] == "MicroG.apk"), None)

    if already_uploaded:
        log.info("MicroG already up to date on this release, skipping upload")
        return

    await upload_with_replace(release, str(new_path))
