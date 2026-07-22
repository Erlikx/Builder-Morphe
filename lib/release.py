import os
from pathlib import Path

import httpx

from .github import download_latest_github_asset

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


async def create_new_release(tag: str, release_name: str, release_body: str = "") -> dict:
    print("🆕 Creating new release:", tag)

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(
            f"https://api.github.com/repos/{REPO}/releases",
            headers=HEADERS,
            json={
                "tag_name": tag,
                "name": release_name,
                "body": release_body,
                "draft": False,
                "prerelease": False,
                "make_latest": "true",
            },
        )
        data = res.json()

    if "id" not in data:
        raise RuntimeError(f"Failed to create release: {data}")

    return data


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
        print("♻️ Replace:", file_name)
        await delete_asset(existing["id"])

    print("📤 Upload:", file_name)
    return await _upload(release["upload_url"], file_path)


async def ensure_release(tag: str, release_name: str, release_body: str) -> dict:
    _assert_configured()
    return await create_new_release(tag, release_name, release_body)


async def upload_patched_apk(release: dict, apk_path: str):
    _assert_configured()
    await upload_with_replace(release, apk_path)


async def upload_microg_once(release: dict):
    _assert_configured()

    print("📦 Fetch MicroG...")
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
        print("✅ MicroG already up to date on this release, skipping upload")
        return

    await upload_with_replace(release, str(new_path))
