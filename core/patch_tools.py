import os
from pathlib import Path
from typing import Callable

from . import log
from . import retry
from .http import new_session

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")


async def fetch_latest_release(owner: str, repo: str, prerelease: bool = False) -> dict:
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/releases"
        if prerelease
        else f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    )

    async def _do(_i: int):
        async with new_session(timeout=30) as client:
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

    return await retry.retry_async(
        _do, retries=5, delay_fn=lambda a: retry.exponential_delay(a, base_delay_ms=1000), label="GitHub request"
    )


async def _download_file(url: str, output_path: Path, expected_size: int | None = None) -> str:
    temp_path = output_path.with_name(output_path.name + ".part")
    downloaded = temp_path.stat().st_size if temp_path.exists() else 0

    headers = {"User-Agent": "python", "Accept": "*/*"}
    if downloaded > 0:
        headers["Range"] = f"bytes={downloaded}-"
        log.download(f"Resuming at {downloaded} bytes")

    mode = "ab" if downloaded > 0 else "wb"

    async with new_session(follow_redirects=True, timeout=None) as client:
        async with client.stream("GET", url, headers=headers) as res:
            if res.status_code >= 400:
                raise RuntimeError(f"HTTP {res.status_code}")

            with open(temp_path, mode) as f:
                async for chunk in res.aiter_content():
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
    log.step(f"Fetching release: {owner}/{repo}")

    release = await fetch_latest_release(owner, repo, prerelease)

    assets = release.get("assets") or []
    if not assets:
        raise RuntimeError(f"Repo {owner}/{repo} has no assets")

    asset = next((a for a in assets if match(a["name"])), None)
    if not asset:
        raise RuntimeError("Matching asset not found")

    log.info(f"Selected: {asset['name']}")

    out_path = Path(asset["name"])

    if out_path.exists():
        size = out_path.stat().st_size
        if size < 1024:
            log.warn("Removing corrupt cache")
            out_path.unlink()
        else:
            log.info(f"Using cached file: {asset['name']}")
            return {
                "name": asset["name"],
                "body": release.get("body") or "",
                "tag": release.get("tag_name") or "",
            }

    async def _do(_i: int):
        await _download_file(asset["browser_download_url"], out_path, asset.get("size"))

    await retry.retry_async(
        _do, retries=5, delay_fn=lambda a: retry.exponential_delay(a, base_delay_ms=1000), label="GitHub download"
    )

    log.success(f"Done: {asset['name']}")

    return {
        "name": asset["name"],
        "body": release.get("body") or "",
        "tag": release.get("tag_name") or "",
    }
