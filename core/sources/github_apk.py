from pathlib import Path

import httpx

from .. import log

APP_TAGS = {
    "instagram": "instagram",
    "speedtest": "Speedtest",
}

DIRECT_REPOS = {
    "inure-github": ("Hamza417", "Inure", "github", "build{version}"),
    "inure-play": ("Hamza417", "Inure", "play", "build{version}"),
}


def _build_tag(tag_template: str, version: str) -> str:
    prefix = tag_template.split("{version}")[0]
    if prefix and version.startswith(prefix):
        return version
    return tag_template.format(version=version)


def _pick_apk_asset(assets: list[dict], name_hint: str | None = None) -> dict | None:
    candidates = [a for a in assets if a["name"].endswith(".apk") or a["name"].endswith(".apkm")]
    if not candidates:
        return None

    if name_hint:
        hinted = [a for a in candidates if name_hint.lower() in a["name"].lower()]
        if hinted:
            candidates = hinted

    arm64 = next((a for a in candidates if "arm64" in a["name"].lower()), None)
    return arm64 or candidates[0]


async def _download_asset(client: httpx.AsyncClient, asset: dict) -> str:
    size_mb = asset["size"] / (1024 * 1024)
    log.download(f"Found file to download: {asset['name']} ({size_mb:.2f} MB)")

    out_dir = Path(__file__).resolve().parent.parent.parent / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    file_path = out_dir / asset["name"]

    log.download("Downloading...")

    async with client.stream("GET", asset["browser_download_url"]) as file_res:
        if file_res.status_code >= 400:
            raise RuntimeError("Failed to download file from GitHub!")
        with open(file_path, "wb") as f:
            async for chunk in file_res.aiter_bytes():
                f.write(chunk)

    downloaded_size = Path(file_path).stat().st_size
    if downloaded_size < 1024:
        raise RuntimeError(f"Downloaded file is too small ({downloaded_size} bytes) - likely an error page")

    log.success(f"Done: {file_path}")
    return str(file_path)


async def download_apk(version: str, app_name: str, force_build: str | None = None) -> str:
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        if app_name in DIRECT_REPOS:
            owner, repo, name_hint, tag_template = DIRECT_REPOS[app_name]

            release_data = None
            wanted_tag = None

            if version and version != "latest":
                wanted_tag = _build_tag(tag_template, version)
                log.step(f"Fetching info from GitHub: {app_name.upper()} ({owner}/{repo}, tag: {wanted_tag})")

                api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{wanted_tag}"
                res = await client.get(api_url, headers={"User-Agent": "Mozilla/5.0 (Python)"})
                if res.status_code < 400:
                    release_data = res.json()
                else:
                    log.warn(f"Tag \"{wanted_tag}\" not found ({res.status_code}), falling back to latest release.")

            if release_data is None:
                log.step(f"Fetching info from GitHub: {app_name.upper()} ({owner}/{repo}, latest release)")
                api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
                res = await client.get(api_url, headers={"User-Agent": "Mozilla/5.0 (Python)"})
                if res.status_code >= 400:
                    raise RuntimeError(f"GitHub API error: {res.status_code}")
                release_data = res.json()

            asset = _pick_apk_asset(release_data.get("assets") or [], name_hint)
            if not asset:
                where = wanted_tag or "latest release"
                raise RuntimeError(f'No .apk or .apkm file found in "{owner}/{repo}" ({where}).')

            return await _download_asset(client, asset)

        tag = APP_TAGS.get(app_name)
        if not tag:
            raise RuntimeError(f'No GitHub tag for "{app_name}".')

        log.step(f"Fetching info from GitHub: {app_name.upper()} (Tag: {tag})")

        api_url = f"https://api.github.com/repos/fuckpdf/Depo/releases/tags/{tag}"
        res = await client.get(api_url, headers={"User-Agent": "Mozilla/5.0 (Python)"})
        if res.status_code >= 400:
            raise RuntimeError(f"GitHub API error: {res.status_code}")

        release_data = res.json()
        asset = _pick_apk_asset(release_data.get("assets") or [])

        if not asset:
            raise RuntimeError(f'No .apk or .apkm file found in GitHub release tagged "{tag}".')

        return await _download_asset(client, asset)


async def get_latest_listing(app_name: str) -> dict:
    if app_name in DIRECT_REPOS:
        owner, repo, _name_hint, _tag_template = DIRECT_REPOS[app_name]
        return {"version": "latest", "href": f"https://github.com/{owner}/{repo}/releases/latest"}

    tag = APP_TAGS.get(app_name)
    if not tag:
        raise RuntimeError(f'No GitHub tag for "{app_name}".')

    return {"version": "latest", "href": f"https://github.com/fuckpdf/Depo/releases/tag/{tag}"}
