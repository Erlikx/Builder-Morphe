import os
import asyncio
import httpx
from pathlib import Path

APP_TAGS = {
    "speedtest": "Speedtest",
    "gboard": "Gboard",
    "wps-office": "WPSOffice",
    "solid-explorer": "SolidExplorer"
}

_TIMEOUT = httpx.Timeout(180.0, connect=20.0)
_RETRIES = 3
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

async def download_apk(version: str, app_name: str, force_build: str | None = None) -> str:
    tag = APP_TAGS.get(app_name)
    if not tag:
        raise Exception(f'GitHub tag not found for "{app_name}"')

    print(f"\n🌐 Fetching from GitHub: {app_name.upper()} (Tag: {tag})")
    api_url = f"https://api.github.com/repos/fuckpdf/Depo/releases/tags/{tag}"

    async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(api_url, headers=_HEADERS)
        response.raise_for_status()
        release_data = response.json()

    asset = next((a for a in release_data.get("assets", []) if a["name"].endswith((".apk", ".apkm"))), None)
    if not asset:
        raise Exception(f'No .apk/.apkm found for tag "{tag}"')

    file_size_mb = asset["size"] / (1024 * 1024)
    print(f"➡️ Found file: {asset['name']} ({file_size_mb:.2f} MB)")

    out_dir = Path(__file__).parent.parent / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / asset["name"]
    temp_path = file_path.with_suffix(file_path.suffix + ".part")

    print("⬇️ Downloading...")
    last_exc = None
    for attempt in range(_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True) as client:
                async with client.stream("GET", asset["browser_download_url"], headers=_HEADERS) as response:
                    response.raise_for_status()
                    with open(temp_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            f.write(chunk)
            temp_path.rename(file_path)
            print(f"📦 SUCCESS: {file_path}")
            return str(file_path)
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError) as e:
            last_exc = e
            temp_path.unlink(missing_ok=True)
            print(f"⚠️ Download failed ({e}); retrying ({attempt + 1}/{_RETRIES})...")
            await asyncio.sleep(2 * (attempt + 1))

    raise Exception(f"Download failed after {_RETRIES} attempts: {last_exc}")

async def get_latest_listing(app_name: str) -> dict:
    tag = APP_TAGS.get(app_name)
    if not tag:
        raise Exception(f'GitHub tag not found for "{app_name}"')
    return {"version": "latest", "href": f"https://github.com/fuckpdf/Depo/releases/tag/{tag}"}
