import os
import requests
from pathlib import Path

def get_headers():
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

def download_asset(owner, repo, match_str, prerelease=False):
    print(f"📦 Fetch release: {owner}/{repo}")
    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    if not prerelease:
        url += "/latest"
        
    res = requests.get(url, headers=get_headers())
    res.raise_for_status()
    
    data = res.json()
    release = data[0] if prerelease and isinstance(data, list) else data
    
    asset = next((a for a in release.get("assets", []) if match_str in a["name"]), None)
    if not asset:
        raise Exception(f"Asset bulunamadı: {match_str}")
        
    print(f"🎯 Selected: {asset['name']}")
    out_path = Path(asset["name"])
    
    if not out_path.exists():
        r = requests.get(asset["browser_download_url"], stream=True)
        r.raise_for_status()
        with open(out_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
                
    return {"path": out_path, "body": release.get("body", ""), "tag": release.get("tag_name", "")}
