import os
import time
import random
import requests
from pathlib import Path

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {
    "User-Agent": "python-morphe",
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {GITHUB_TOKEN}",
}


def _jitter(base: float) -> float:
    return base + random.uniform(0, 0.3)


def _with_retry(fn, retries=5, base_delay=1.0):
    last_err = None
    for i in range(retries):
        try:
            return fn()
        except Exception as e:
            last_err = e
            delay = _jitter(base_delay * (2 ** i))
            print(f"  🔁 Retry {i+1}/{retries} in {delay:.1f}s – {e}")
            time.sleep(delay)
    raise last_err


def fetch_latest_release(owner: str, repo: str, prerelease: bool = False) -> dict:
    if prerelease:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    else:
        url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"

    def _do():
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if prerelease:
            if not isinstance(data, list) or not data:
                raise RuntimeError("No releases found")
            return data[0]
        return data

    return _with_retry(_do)


def download_file(url: str, dest: str, expected_size: int | None = None):
    dest_path = Path(dest)
    temp_path = dest_path.with_suffix(dest_path.suffix + ".part")

    downloaded = 0
    headers = {"User-Agent": "python-morphe", "Accept": "*/*"}

    if temp_path.exists():
        downloaded = temp_path.stat().st_size
        headers["Range"] = f"bytes={downloaded}-"
        print(f"  ↩️  Resuming at {downloaded} bytes")

    with requests.get(url, headers=headers, stream=True, timeout=60) as resp:
        resp.raise_for_status()

        # Server may ignore the Range header and send the whole file back
        # (status 200) instead of just the remainder (status 206). If we
        # blindly append in that case the result is corrupted.
        if downloaded > 0 and resp.status_code != 206:
            print("  ⚠️  Server did not honor Range request, restarting download")
            downloaded = 0
            mode = "wb"
        else:
            mode = "ab" if downloaded > 0 else "wb"

        with open(temp_path, mode) as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                f.write(chunk)
                downloaded += len(chunk)

    if expected_size and downloaded != expected_size:
        temp_path.unlink(missing_ok=True)
        raise RuntimeError(f"Size mismatch: got {downloaded}, expected {expected_size}")

    temp_path.rename(dest_path)
    return str(dest_path)


def download_latest_github_asset(owner: str, repo: str, match_fn, prerelease: bool = False) -> dict:
    print(f"\n  📦 Fetching release: {owner}/{repo}")
    release = fetch_latest_release(owner, repo, prerelease)

    assets = release.get("assets", [])
    if not assets:
        raise RuntimeError(f"{owner}/{repo} has no assets")

    asset = next((a for a in assets if match_fn(a["name"])), None)
    if not asset:
        raise RuntimeError(f"No matching asset found in {owner}/{repo}")

    print(f"  🎯 Selected: {asset['name']}")

    dest = Path(asset["name"])
    if dest.exists():
        size = dest.stat().st_size
        expected = asset.get("size")
        if size < 1024 or (expected and size != expected):
            print("  🧹 Removing stale/corrupt cache")
            dest.unlink()
        else:
            print(f"  ⚡ Using cache: {asset['name']}")
            return {
                "name": asset["name"],
                "body": release.get("body", ""),
                "tag":  release.get("tag_name", ""),
            }

    def _do():
        download_file(asset["browser_download_url"], asset["name"], asset["size"])

    _with_retry(_do)
    print(f"  ✅ Done: {asset['name']}")

    return {
        "name": asset["name"],
        "body": release.get("body", ""),
        "tag":  release.get("tag_name", ""),
    }
