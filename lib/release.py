import os
import json
import requests
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("GITHUB_REPOSITORY")

def assert_configured():
    if not TOKEN:
        raise Exception("Missing GITHUB_TOKEN")
    if not REPO:
        raise Exception("Missing GITHUB_REPOSITORY")

def github_request(method, path, data=None, headers_extra=None):
    assert_configured()
    url = f"https://api.github.com{path}"
    headers = {
        "User-Agent": "node",
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    if headers_extra:
        headers.update(headers_extra)

    if data is not None:
        data = json.dumps(data)

    resp = requests.request(method, url, headers=headers, data=data)
    if resp.status_code not in (200, 201, 204):
        raise Exception(f"GitHub API error: {resp.status_code} {resp.text}")
    if resp.status_code == 204:
        return {}
    return resp.json()

def create_release(tag, name, body=""):
    logger.info(f"🆕 Creating new release: {tag}")
    data = {
        "tag_name": tag,
        "name": name,
        "body": body,
        "draft": False,
        "prerelease": False,
        "make_latest": "true",
    }
    return github_request("POST", f"/repos/{REPO}/releases", data)

def get_assets(release_id):
    return github_request("GET", f"/repos/{REPO}/releases/{release_id}/assets")

def delete_asset(asset_id):
    return github_request("DELETE", f"/repos/{REPO}/releases/assets/{asset_id}")

def upload_asset(upload_url, file_path):
    file_path = Path(file_path)
    file_name = file_path.name
    with open(file_path, "rb") as f:
        data = f.read()

    url = upload_url.replace("{?name,label}", f"?name={file_name}")
    headers_extra = {
        "Content-Type": "application/vnd.android.package-archive",
    }
    resp = requests.post(url, headers={
        "Authorization": f"Bearer {TOKEN}",
        "User-Agent": "node",
        **headers_extra,
    }, data=data)
    if resp.status_code not in (200, 201):
        raise Exception(f"Upload failed: {resp.status_code} {resp.text}")
    return resp.json()

def upload_with_replace(release, file_path):
    file_name = Path(file_path).name
    assets = get_assets(release["id"])
    for asset in assets:
        if asset["name"] == file_name:
            logger.info(f"♻️ Replace: {file_name}")
            delete_asset(asset["id"])
            break

    logger.info(f"📤 Upload: {file_name}")
    return upload_asset(release["upload_url"], file_path)

def ensure_release(tag, name, body):
    assert_configured()
    return create_release(tag, name, body)

def upload_patched_apk(release, apk_path):
    assert_configured()
    upload_with_replace(release, apk_path)

def upload_microg_once(release):
    assert_configured()
    from .github import download_latest_github_asset
    logger.info("📦 Fetch MicroG...")
    microg_result = download_latest_github_asset(
        owner="MorpheApp",
        repo="MicroG-RE",
        match_func=lambda n: n.endswith(".apk")
    )

    original_path = Path(microg_result["name"])
    new_path = Path("MicroG.apk")
    if original_path.exists() and original_path != new_path:
        original_path.rename(new_path)

    assets = get_assets(release["id"])
    for asset in assets:
        if asset["name"] == "MicroG.apk":
            logger.info("✅ MicroG already up to date on this release, skipping upload")
            return

    upload_with_replace(release, new_path)    upload_with_replace(release, new_path)
