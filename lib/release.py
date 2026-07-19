import os
import requests
from pathlib import Path
from urllib.parse import urlencode, quote

from .github import download_latest_github_asset

TOKEN = os.environ.get("GITHUB_TOKEN", "")
REPO  = os.environ.get("GITHUB_REPOSITORY", "")

HEADERS = {
    "User-Agent":  "python-morphe",
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}


def _assert_configured():
    if not TOKEN:
        raise RuntimeError("Missing GITHUB_TOKEN")
    if not REPO:
        raise RuntimeError("Missing GITHUB_REPOSITORY")


def create_release(tag: str, name: str, body: str = "") -> dict:
    print(f"  🆕 Creating release: {tag}")
    resp = requests.post(
        f"https://api.github.com/repos/{REPO}/releases",
        headers=HEADERS,
        json={
            "tag_name":    tag,
            "name":        name,
            "body":        body,
            "draft":       False,
            "prerelease":  False,
            "make_latest": "true",
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    if "id" not in data:
        raise RuntimeError(f"Failed to create release: {data}")
    return data


def get_assets(release_id: int) -> list:
    resp = requests.get(
        f"https://api.github.com/repos/{REPO}/releases/{release_id}/assets",
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def delete_asset(asset_id: int):
    resp = requests.delete(
        f"https://api.github.com/repos/{REPO}/releases/assets/{asset_id}",
        headers=HEADERS,
        timeout=30,
    )
    resp.raise_for_status()


def upload_asset(upload_url: str, file_path: str):
    file_name = Path(file_path).name
    clean_url  = upload_url.replace("{?name,label}", "")
    full_url   = f"{clean_url}?name={quote(file_name)}"

    data = Path(file_path).read_bytes()
    resp = requests.post(
        full_url,
        headers={
            **HEADERS,
            "Content-Type":   "application/vnd.android.package-archive",
            "Content-Length": str(len(data)),
        },
        data=data,
        timeout=600,
    )
    resp.raise_for_status()
    return resp.json()


def upload_with_replace(release: dict, file_path: str):
    file_name = Path(file_path).name
    assets    = get_assets(release["id"])
    existing  = next((a for a in assets if a["name"] == file_name), None)

    if existing:
        print(f"  ♻️  Replacing: {file_name}")
        delete_asset(existing["id"])

    print(f"  📤 Uploading: {file_name}")
    return upload_asset(release["upload_url"], file_path)


def ensure_release(tag: str, name: str, body: str) -> dict:
    _assert_configured()
    return create_release(tag, name, body)


def upload_patched_apk(release: dict, apk_path: str):
    _assert_configured()
    upload_with_replace(release, apk_path)


def upload_microg_once(release: dict):
    _assert_configured()
    print("  📦 Fetching MicroG…")

    microg = download_latest_github_asset(
        owner="MorpheApp",
        repo="MicroG-RE",
        match_fn=lambda n: n.endswith(".apk"),
    )

    original = Path(microg["name"]).resolve()
    target   = Path("MicroG.apk").resolve()

    if original.exists() and original != target:
        original.rename(target)

    assets = get_assets(release["id"])
    if any(a["name"] == "MicroG.apk" for a in assets):
        print("  ✅ MicroG already on this release, skipping")
        return

    upload_with_replace(release, str(target))
