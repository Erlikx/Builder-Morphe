import os
import asyncio
import httpx
from pathlib import Path

_TIMEOUT = httpx.Timeout(60.0, connect=20.0)
_RETRIES = 3

async def fetch_latest_release(owner: str, repo: str, prerelease: bool = False) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases" if prerelease else f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}"
    }

    last_exc = None
    for attempt in range(_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json()

                if prerelease:
                    if not isinstance(data, list) or len(data) == 0:
                        raise Exception("No releases found")
                    return data[0]
                return data
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
            last_exc = e
            print(f"⚠️ API request failed ({e}); retrying ({attempt + 1}/{_RETRIES})...")
            await asyncio.sleep(2 * (attempt + 1))

    raise Exception(f"API request failed after {_RETRIES} attempts: {last_exc}")

async def download_asset_with_resume(url: str, output_path: str, expected_size: int | None = None) -> str:
    file_path = Path(output_path).resolve()
    temp_path = file_path.with_suffix(file_path.suffix + ".part")

    last_exc = None
    for attempt in range(_RETRIES):
        downloaded = temp_path.stat().st_size if temp_path.exists() else 0
        headers = {"Accept": "*/*"}

        if downloaded > 0:
            headers["Range"] = f"bytes={downloaded}-"
            print(f"↩️ Resume at {downloaded} bytes")

        mode = "ab" if downloaded > 0 else "wb"

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                async with client.stream("GET", url, headers=headers, follow_redirects=True) as response:
                    response.raise_for_status()

                    with open(temp_path, mode) as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            f.write(chunk)
                            downloaded += len(chunk)

                    if expected_size and downloaded != expected_size:
                        temp_path.unlink(missing_ok=True)
                        raise Exception(f"Size mismatch: {downloaded}/{expected_size}")

                    temp_path.rename(file_path)
                    return str(file_path)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
            last_exc = e
            print(f"⚠️ Download interrupted ({e}); retrying ({attempt + 1}/{_RETRIES})...")
            await asyncio.sleep(2 * (attempt + 1))

    raise Exception(f"Download failed after {_RETRIES} attempts: {last_exc}")

async def download_latest_github_asset(owner: str, repo: str, prerelease: bool = False, match_fn: callable = None) -> dict:
    print(f"\n📦 Fetch release: {owner}/{repo}")
    release = await fetch_latest_release(owner, repo, prerelease)

    if not release.get("assets"):
        raise Exception(f"Repo {owner}/{repo} has no assets")

    asset = next((a for a in release["assets"] if match_fn(a["name"])), None)
    if not asset:
        raise Exception("❌ Asset not found")

    print(f"🎯 Selected: {asset['name']}")

    if Path(asset["name"]).exists() and Path(asset["name"]).stat().st_size > 1024:
        print("⚡ Skip cached:", asset["name"])
        return {"name": asset["name"], "body": release.get("body", ""), "tag": release.get("tag_name", "")}

    print("⬇️ Downloading...")
    await download_asset_with_resume(asset["browser_download_url"], asset["name"], asset["size"])
    print("✅ Done:", asset["name"])

    return {"name": asset["name"], "body": release.get("body", ""), "tag": release.get("tag_name", "")}
