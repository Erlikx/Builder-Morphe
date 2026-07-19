import os
import requests
import time
import random
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def sleep_with_jitter(ms):
    time.sleep((ms + random.randint(0, 300)) / 1000.0)

def with_retry(fn, retries=5, base_delay=1000):
    last_err = None
    for i in range(retries):
        try:
            return fn()
        except Exception as e:
            last_err = e
            delay = base_delay * (2 ** i) + random.randint(0, 300)
            logger.info(f"🔁 Retry {i+1}/{retries} in {delay}ms - {str(e)}")
            sleep_with_jitter(delay)
    raise last_err

def fetch_latest_release(owner, repo, prerelease=False):
    token = os.environ.get("GITHUB_TOKEN")
    headers = {
        "User-Agent": "node",
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"https://api.github.com/repos/{owner}/{repo}/releases"
    if not prerelease:
        url += "/latest"

    def _fetch():
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            raise Exception(f"GitHub API error: {resp.status_code}")
        data = resp.json()
        if prerelease:
            if not data:
                raise Exception("No releases found")
            return data[0]
        return data

    return with_retry(_fetch)

def download_file(url, output_path, expected_size=None):
    output_path = Path(output_path)
    temp_path = output_path.with_suffix(output_path.suffix + ".part")
    downloaded = 0

    if temp_path.exists():
        downloaded = temp_path.stat().st_size

    headers = {"User-Agent": "node", "Accept": "*/*"}
    if downloaded > 0:
        headers["Range"] = f"bytes={downloaded}-"
        logger.info(f"↩️ Resume at {downloaded} bytes")

    with requests.get(url, headers=headers, stream=True) as r:
        if r.status_code >= 400:
            raise Exception(f"HTTP {r.status_code}")
        mode = "ab" if downloaded > 0 else "wb"
        with open(temp_path, mode) as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

    if expected_size and downloaded != expected_size:
        temp_path.unlink()
        raise Exception(f"Size mismatch: {downloaded}/{expected_size}")

    temp_path.rename(output_path)
    return output_path

def download_latest_github_asset(owner, repo, prerelease=False, match_func=None):
    logger.info(f"\n📦 Fetch release: {owner}/{repo}")

    release = fetch_latest_release(owner, repo, prerelease)

    if not release.get("assets"):
        raise Exception(f"Repo {owner}/{repo} has no assets")

    asset = None
    for a in release["assets"]:
        if match_func and match_func(a["name"]):
            asset = a
            break
    if not asset:
        raise Exception(f"❌ No matching asset found")

    logger.info(f"🎯 Selected: {asset['name']}")

    if Path(asset["name"]).exists():
        size = Path(asset["name"]).stat().st_size
        if size < 1024:
            logger.info("🧹 Corrupt cache removed")
            Path(asset["name"]).unlink()
        else:
            logger.info(f"⚡ Skip cached: {asset['name']}")
            return {
                "name": asset["name"],
                "body": release.get("body", ""),
                "tag": release.get("tag_name", "")
            }

    def _download():
        download_file(asset["browser_download_url"], asset["name"], asset["size"])

    with_retry(_download)

    logger.info(f"✅ Done: {asset['name']}")
    return {
        "name": asset["name"],
        "body": release.get("body", ""),
        "tag": release.get("tag_name", "")
    }
