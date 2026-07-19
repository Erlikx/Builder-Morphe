import os
import requests
from lib.github import get_headers

def create_github_release(tag, name, body, assets):
    repo = os.environ.get("GITHUB_REPOSITORY", "fuckpdf/youtube-morphe")
    print(f"\n📢 Creating New Release: {tag}")
    url = f"https://api.github.com/repos/{repo}/releases"
    
    payload = {"tag_name": tag, "name": name, "body": body, "draft": False, "prerelease": False}
    res = requests.post(url, headers=get_headers(), json=payload)
    res.raise_for_status()
    release = res.json()
    upload_base = release["upload_url"].split("{")[0]
    
    for asset in assets:
        print(f"📤 Upload: {asset.name}")
        headers = get_headers()
        headers["Content-Type"] = "application/vnd.android.package-archive"
        upload_url = f"{upload_base}?name={asset.name}"
        with open(asset, "rb") as f:
            requests.post(upload_url, headers=headers, data=f).raise_for_status()
            
    print("🎉 All apps successfully published under one release!")
