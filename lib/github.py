import asyncio
import os
import random
from pathlib import Path
from typing import Callable

import httpx

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


def _jitter(ms: int) -> int:
    return ms + random.randint(0, 300)


async def with_retry(fn: Callable, retries: int = 5, base_delay_ms: int = 1000):
    last_err: Exception | None = None

    for i in range(retries):
        try:
            return await fn(i)
        except Exception as err:  # noqa: BLE001 - mirrors original catch-all retry
            last_err = err
            delay_ms = _jitter(base_delay_ms * (2 ** i))
            print(f"🔁 Retry {i + 1}/{retries} in {delay_ms}ms - {err}")
            await asyncio.sleep(delay_ms / 1000)

    raise last_err


async def fetch_latest_release(owner: str, repo: str, prerelease: bool = False) -> dict:
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/releases"
        if prerelease
        else f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    )

    async def _do(_i: int):
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.get(
                url,
                headers={
                    "User-Agent": "python",
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {GITHUB_TOKEN}",
                },
            )
            if res.status_code >= 400:
                raise RuntimeError(f"GitHub API error: {res.status_code}")

            data = res.json()

            if prerelease:
                if not isinstance(data, list) or not data:
                    raise RuntimeError("No releases found")
                return data[0]

            return data

    return await with_retry(_do)


async def _download_file(url: str, output_path: Path, expected_size: int | None = None) -> str:
    temp_path = output_path.with_name(output_path.name + ".part")
    downloaded = temp_path.stat().st_size if temp_path.exists() else 0

    headers = {"User-Agent": "python", "Accept": "*/*"}
    if downloaded > 0:
        headers["Range"] = f"bytes={downloaded}-"
        print(f"↩️ Resume at {downloaded} bytes")

    mode = "ab" if downloaded > 0 else "wb"

    async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
        async with client.stream("GET", url, headers=headers) as res:
            if res.status_code >= 400:
                raise RuntimeError(f"HTTP {res.status_code}")

            with open(temp_path, mode) as f:
                async for chunk in res.aiter_bytes():
                    f.write(chunk)
                    downloaded += len(chunk)

    if expected_size and downloaded != expected_size:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Size mismatch: {downloaded}/{expected_size}")

    temp_path.rename(output_path)
    return str(output_path)


async def download_latest_github_asset(
    owner: str, repo: str, match: Callable[[str], bool], prerelease: bool = False
) -> dict:
    print(f"\n📦 Fetch release: {owner}/{repo}")

    release = await fetch_latest_release(owner, repo, prerelease)

    assets = release.get("assets") or []
    if not assets:
        raise RuntimeError(f"Repo {owner}/{repo} has no assets")

    asset = next((a for a in assets if match(a["name"])), None)
    if not asset:
        raise RuntimeError("❌ Matching asset not found")

    print("🎯 Selected:", asset["name"])

    out_path = Path(asset["name"])

    if out_path.exists():
        size = out_path.stat().st_size
        if size < 1024:
            print("🧹 Corrupt cache removed")
            out_path.unlink()
        else:
            print("⚡ Skip cached:", asset["name"])
            return {
                "name": asset["name"],
                "body": release.get("body") or "",
                "tag": release.get("tag_name") or "",
            }

    async def _do(_i: int):
        await _download_file(asset["browser_download_url"], out_path, asset.get("size"))

    await with_retry(_do)

    print("✅ Done:", asset["name"])

    return {
        "name": asset["name"],
        "body": release.get("body") or "",
        "tag": release.get("tag_name") or "",
    }
