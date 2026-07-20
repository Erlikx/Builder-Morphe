import os
import asyncio
import httpx
from pathlib import Path

_TIMEOUT = httpx.Timeout(60.0, connect=20.0)
_RETRIES = 5
_RETRY_STATUS = (429, 500, 502, 503, 504)
_HEADERS_BASE = {
    "Accept": "application/vnd.github+json",
    "User-Agent": "Builder-Morphe-Actions",
    "X-GitHub-Api-Version": "2022-11-28",
}

async def _sleep_for_retry(exc, attempt):
    delay = min(3 * (2 ** attempt), 30)
    if isinstance(exc, httpx.HTTPStatusError):
        raw = exc.response.headers.get("Retry-After")
        if raw and raw.isdigit():
            delay = max(int(raw), delay)
    await asyncio.sleep(delay)

async def fetch_latest_release(owner: str, repo: str, prerelease: bool = False) -> dict:
    if prerelease:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases?per_page=1"
    else:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

    headers = dict(_HEADERS_BASE)
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

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
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in _RETRY_STATUS:
                raise
            last_exc = e
            print(f"⚠️ API returned {e.response.status_code}; retrying ({attempt + 1}/{_RETRIES})...")
            await _sleep_for_retry(e, attempt)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
            last_exc = e
            print(f"⚠️ API request failed ({e}); retrying ({attempt + 1}/{_RETRIES})...")
            await _sleep_for_retry(e, attempt)

    raise Exception(f"API request failed after {_RETRIES} attempts: {last_exc}")

async def download_asset_with_resume(url: str, output_path: str, expected_size: int | None = None) -> str:
    file_path = Path(output_path).resolve()
    temp_path = file_path.with_suffix(file_path.suffix + ".part")

    last_exc = None
    for attempt in range(_RETRIES):
        downloaded = temp_path.stat().st_size if temp_path.exists() else 0
        headers = {"Accept": "*/*", "User-Agent": "Builder-Morphe-Actions"}

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
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in _RETRY_STATUS:
                raise
            last_exc = e
            print(f"⚠️ Download server error {e.response.status_code}; retrying ({attempt + 1}/{_RETRIES})...")
            await _sleep_for_retry(e, attempt)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
            last_exc = e
            print(f"⚠️ Download interrupted ({e}); retrying ({attempt + 1}/{_RETRIES})...")
            await _sleep_for_retry(e, attempt)

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
