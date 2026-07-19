import os
import requests
from urllib.parse import quote
from .github import download_latest_github_asset

TOKEN = os.environ.get("GITHUB_TOKEN")
REPO = os.environ.get("GITHUB_REPOSITORY")

def get_headers():
    return {
        "User-Agent": "python",
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/vnd.github+json"
    }

def ensure_release(tag: str, release_name: str, release_body: str):
    res = requests.post(
        f"https://api.github.com/repos/{REPO}/releases",
        headers=get_headers(),
        json={
            "tag_name": tag,
            "name": release_name,
            "body": release_body,
            "draft": False,
            "prerelease": False,
            "make_latest": "true"
        }
    )
    data = res.json()
    if "id" not in data:
        raise Exception(f"Failed to create release: {data}")
    return data

def upload_patched_apk(release: dict, apkPath: str):
    file_name = os.path.basename(apkPath)
    res = requests.get(f"https://api.github.com/repos/{REPO}/releases/{release['id']}/assets", headers=get_headers())
    assets = res.json()
    exist = next((a for a in assets if a["name"] == file_name), None)
    
    if exist:
        requests.delete(f"https://api.github.com/repos/{REPO}/releases/assets/{exist['id']}", headers=get_headers())
        
    upload_url = release["upload_url"].replace("{?name,label}", f"?name={quote(file_name)}")
    headers = get_headers()
    headers["Content-Type"] = "application/vnd.android.package-archive"
    headers["Content-Length"] = str(os.path.getsize(apkPath))
    
    with open(apkPath, "rb") as f:
        requests.post(upload_url, headers=headers, data=f)

def upload_microg_once(release: dict):
    asset = download_latest_github_asset("MorpheApp", "MicroG-RE", lambda n: n.endswith(".apk"))
    new_path = "MicroG.apk"
    if os.path.exists(asset["name"]) and asset["name"] != new_path:
        os.rename(asset["name"], new_path)
    upload_patched_apk(release, new_path)
