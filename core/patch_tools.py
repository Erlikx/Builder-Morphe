import re
from collections.abc import Callable
from pathlib import Path

from tenacity import retry, stop_after_attempt

from . import log
from . import retry as retry_conf
from .http import new_session
from .settings import settings


_TAG_RE = re.compile(r"^v?(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.\-]+))?")


def release_sort_key(release: dict) -> tuple:
    """Sort key ordering GitHub releases by semantic version, highest last.

    GitHub's /releases endpoint is ordered by creation date, not by version,
    so ``data[0]`` can be an older tag (e.g. dev.9 listed before dev.11).
    Follows semver precedence: a stable release outranks its own pre-releases
    (1.44.0 > 1.44.0-dev.11) and pre-release parts compare numerically
    (dev.11 > dev.9). Drafts and unparsable tags sort lowest.
    """
    if release.get("draft"):
        return (0, (), 0, ())

    match = _TAG_RE.match(str(release.get("tag_name") or ""))
    if not match:
        return (0, (), 0, ())

    core = tuple(int(p) for p in match.group(1).split("."))
    pre = match.group(2)
    if pre is None:
        return (1, core, 1, ())

    idents = tuple((0, int(i), "") if i.isdigit() else (1, 0, i) for i in pre.split("."))
    return (1, core, 0, idents)


def pick_highest_release(releases: list[dict]) -> dict:
    """Return the release with the highest semantic version (drafts ignored)."""
    published = [r for r in releases if not r.get("draft")]
    if not published:
        raise RuntimeError("No published releases found")
    return max(published, key=release_sort_key)


async def fetch_latest_release(owner: str, repo: str, prerelease: bool = False) -> dict:
    url = (
        f"https://api.github.com/repos/{owner}/{repo}/releases"
        if prerelease
        else f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    )

    @retry(
        stop=stop_after_attempt(5),
        wait=retry_conf.exponential_with_jitter(max=30.0),
        before_sleep=retry_conf.before_sleep("GitHub request"),
        reraise=True,
    )
    async def _do():
        async with new_session(timeout=30) as client:
            res = await client.get(
                url,
                headers={
                    "User-Agent": "python",
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {settings.github_token.get_secret_value()}",
                },
            )
            if res.status_code >= 400:
                raise RuntimeError(f"GitHub API error: {res.status_code}")

            data = res.json()

            if prerelease:
                if not isinstance(data, list) or not data:
                    raise RuntimeError("No releases found")
                return pick_highest_release(data)

            return data

    return await _do()


async def _download_file(url: str, output_path: Path, expected_size: int | None = None) -> str:
    temp_path = output_path.with_name(output_path.name + ".part")
    downloaded = temp_path.stat().st_size if temp_path.exists() else 0

    headers = {"User-Agent": "python", "Accept": "*/*"}
    if downloaded > 0:
        headers["Range"] = f"bytes={downloaded}-"
        log.download(f"Resuming at {downloaded} bytes")

    mode = "ab" if downloaded > 0 else "wb"

    async with (
        new_session(follow_redirects=True, timeout=None) as client,
        client.stream("GET", url, headers=headers) as res,
    ):
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

    log.info(f"Selected: {asset['name']} (tag {release.get('tag_name')}, prerelease={bool(release.get('prerelease'))})")

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
                "prerelease": bool(release.get("prerelease")),
            }

    @retry(
        stop=stop_after_attempt(5),
        wait=retry_conf.exponential_with_jitter(max=30.0),
        before_sleep=retry_conf.before_sleep("GitHub download"),
        reraise=True,
    )
    async def _do():
        await _download_file(asset["browser_download_url"], out_path, asset.get("size"))

    await _do()

    log.success(f"Done: {asset['name']}")

    return {
        "name": asset["name"],
        "body": release.get("body") or "",
        "tag": release.get("tag_name") or "",
        "prerelease": bool(release.get("prerelease")),
    }
