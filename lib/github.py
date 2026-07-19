import os
from .http import request_with_retry, download_file_pro

def fetch_latest_release(owner: str, repo: str, prerelease: bool = False):
    url = f"https://api.github.com/repos/{owner}/{repo}/releases" if prerelease else f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    headers = {"User-Agent": "python", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    res = request_with_retry(url, headers=headers)
    data = res.json()
    if prerelease:
        if not isinstance(data, list) or len(data) == 0:
            raise Exception("No releases found")
        return data[0]
    return data

def download_latest_github_asset(owner: str, repo: str, match, prerelease: bool = False):
    release = fetch_latest_release(owner, repo, prerelease)
    assets = release.get("assets", [])
    if not assets:
        raise Exception("No assets")
    asset = next((a for a in assets if match(a["name"])), None)
    if not asset:
        raise Exception("Asset not found")
    if os.path.exists(asset["name"]):
        if os.path.getsize(asset["name"]) < 1024:
            os.remove(asset["name"])
        else:
            return {"name": asset["name"], "body": release.get("body", ""), "tag": release.get("tag_name", "")}
    download_file_pro(asset["browser_download_url"], asset["name"], asset["size"])
    return {"name": asset["name"], "body": release.get("body", ""), "tag": release.get("tag_name", "")}
