import os
import httpx
from pathlib import Path
from github import download_latest_github_asset

TOKEN = os.getenv("GITHUB_TOKEN")
REPO = os.getenv("GITHUB_REPOSITORY")

def assert_configured():
    if not TOKEN: raise Exception("Missing GITHUB_TOKEN")
    if not REPO: raise Exception("Missing GITHUB_REPOSITORY")

async def create_new_release(tag: str, release_name: str, release_body: str = "") -> dict:
    print(f"🆕 Creating new release: {tag}")
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "tag_name": tag,
        "name": release_name,
        "body": release_body,
        "draft": False,
        "prerelease": False,
        "make_latest": "true"
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(f"https://api.github.com/repos/{REPO}/releases", headers=headers, json=payload)
        response.raise_for_status()
        return response.json()

async def get_assets(release_id: int) -> list:
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.github.com/repos/{REPO}/releases/{release_id}/assets", headers=headers)
        response.raise_for_status()
        return response.json()

async def delete_asset(asset_id: int):
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {TOKEN}"}
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"https://api.github.com/repos/{REPO}/releases/assets/{asset_id}", headers=headers)
        response.raise_for_status()

async def upload_asset(upload_url: str, file_path: str):
    file_name = Path(file_path).name
    data = Path(file_path).read_bytes()
    
    # Clean up the {?name,label} template from GitHub API
    clean_url = upload_url.replace("{?name,label}", f"?name={httpx.URL(file_name).raw_path.decode()}")
    
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/vnd.android.package-archive",
        "Content-Length": str(len(data))
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(clean_url, headers=headers, content=data)
        response.raise_for_status()
        return response.json()

async def upload_with_replace(release: dict, file_path: str):
    file_name = Path(file_path).name
    assets = await get_assets(release["id"])
    existing = next((a for a in assets if a["name"] == file_name), None)
    
    if existing:
        print(f"♻️ Replace: {file_name}")
        await delete_asset(existing["id"])
        
    print(f"📤 Upload: {file_name}")
    return await upload_asset(release["upload_url"], file_path)

async def ensure_release(tag: str, release_name: str, release_body: str) -> dict:
    assert_configured()
    return await create_new_release(tag, release_name, release_body)

async def upload_patched_apk(release: dict, apk_path: str):
    assert_configured()
    await upload_with_replace(release, apk_path)

async def upload_microg_once(release: dict):
    assert_configured()
    print("📦 Fetch MicroG...")
    microg_result = await download_latest_github_asset(
        owner="MorpheApp", repo="MicroG-RE", match_fn=lambda n: n.endswith(".apk")
    )
    
    original_path = Path(microg_result["name"]).resolve()
    new_path = Path("MicroG.apk").resolve()
    
    if original_path.exists() and original_path != new_path:
        original_path.rename(new_path)
        
    assets = await get_assets(release["id"])
    if any(a["name"] == "MicroG.apk" for a in assets):
        print("✅ MicroG already up to date on this release, skipping upload")
        return
        
    await upload_with_replace(release, str(new_path))
