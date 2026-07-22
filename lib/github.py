import os
from pathlib import Path
from typing import Callable

import httpx

TOKEN = os.environ.get("GITHUB_TOKEN", "")

API_HEADERS = {
    "User-Agent": "python",
    "Accept": "application/vnd.github+json",
}
if TOKEN:
    API_HEADERS["Authorization"] = f"Bearer {TOKEN}"

APP_TAGS = {
    "instagram": "instagram",
    "speedtest": "Speedtest",
    "pydroid3": "Pydroid3",
    "github": "github",
    "niagara-launcher": "NiagaraLauncher",
    "solid-explorer": "SolidExplorer",
    "gboard": "Gboard",
    "wps-office": "WPSOffice",
    "smart-launcher": "SmartLauncher",
    "brave": "brave",
}


async def download_apk(version: str, app_name: str, force_build: str | None = None) -> str:
    tag = APP_TAGS.get(app_name)
    if not tag:
        raise RuntimeError(f'"{app_name}" için GitHub tag\'i bulunamadı.')

    print(f"\n🌐 GitHub'dan bilgi alınıyor: {app_name.upper()} (Tag: {tag})")

    api_url = f"https://api.github.com/repos/fuckpdf/Depo/releases/tags/{tag}"

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        res = await client.get(api_url, headers={"User-Agent": "Mozilla/5.0 (Python)"})
        if res.status_code >= 400:
            raise RuntimeError(f"GitHub API Hatası: {res.status_code}")

        release_data = res.json()
        asset = next(
            (a for a in release_data["assets"] if a["name"].endswith(".apk") or a["name"].endswith(".apkm")),
            None,
        )

        if not asset:
            raise RuntimeError(f'"{tag}" etiketli GitHub sürümünde .apk veya .apkm dosyası bulunamadı.')

        size_mb = asset["size"] / (1024 * 1024)
        print(f"➡️ İndirilecek dosya bulundu: {asset['name']} ({size_mb:.2f} MB)")

        out_dir = Path(__file__).resolve().parent.parent / "downloads"
        out_dir.mkdir(parents=True, exist_ok=True)
        file_path = out_dir / asset["name"]

        print("⬇️ İndiriliyor...")

        async with client.stream("GET", asset["browser_download_url"]) as file_res:
            if file_res.status_code >= 400:
                raise RuntimeError("Dosya GitHub'dan indirilemedi!")
            with open(file_path, "wb") as f:
                async for chunk in file_res.aiter_bytes():
                    f.write(chunk)

    downloaded_size = Path(file_path).stat().st_size
    if downloaded_size < 1024:
        raise RuntimeError(f"İndirilen dosya çok küçük ({downloaded_size} bayt) - muhtemelen hata sayfası indi")

    print(f"📦 BAŞARILI: {file_path}")
    return str(file_path)


async def get_latest_listing(app_name: str) -> dict:
    tag = APP_TAGS.get(app_name)
    if not tag:
        raise RuntimeError(f'"{app_name}" için GitHub tag\'i bulunamadı.')

    return {"version": "latest", "href": f"https://github.com/fuckpdf/Depo/releases/tag/{tag}"}


async def download_latest_github_asset(
    owner: str,
    repo: str,
    match: Callable[[str], bool],
    prerelease: bool = False,
) -> dict:
    """En son (gerekirse prerelease dahil) GitHub release'inden `match` ile eşleşen
    ilk asset'i indirir ve {"name", "tag", "body"} döndürür."""

    print(f"\n🌐 GitHub release aranıyor: {owner}/{repo} (prerelease={prerelease})")

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        if prerelease:
            res = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/releases",
                headers=API_HEADERS,
                params={"per_page": 10},
            )
            if res.status_code >= 400:
                raise RuntimeError(f"GitHub API Hatası: {res.status_code}")

            releases = res.json()
            release_data = next(
                (r for r in releases if any(match(a["name"]) for a in r.get("assets", []))),
                None,
            )
            if not release_data:
                raise RuntimeError(f'"{owner}/{repo}" içinde eşleşen bir release bulunamadı.')
        else:
            res = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
                headers=API_HEADERS,
            )
            if res.status_code >= 400:
                raise RuntimeError(f"GitHub API Hatası: {res.status_code}")

            release_data = res.json()

        asset = next((a for a in release_data.get("assets", []) if match(a["name"])), None)
        if not asset:
            raise RuntimeError(f'"{owner}/{repo}" release\'inde eşleşen dosya bulunamadı.')

        size_mb = asset["size"] / (1024 * 1024)
        print(f"➡️ İndirilecek dosya bulundu: {asset['name']} ({size_mb:.2f} MB)")

        file_path = Path.cwd() / asset["name"]

        print("⬇️ İndiriliyor...")
        async with client.stream(
            "GET", asset["browser_download_url"], headers={"User-Agent": "Mozilla/5.0 (Python)"}
        ) as file_res:
            if file_res.status_code >= 400:
                raise RuntimeError("Dosya GitHub'dan indirilemedi!")
            with open(file_path, "wb") as f:
                async for chunk in file_res.aiter_bytes():
                    f.write(chunk)

    downloaded_size = file_path.stat().st_size
    if downloaded_size < 1024:
        raise RuntimeError(f"İndirilen dosya çok küçük ({downloaded_size} bayt) - muhtemelen hata sayfası indi")

    print(f"📦 BAŞARILI: {file_path}")

    return {
        "name": asset["name"],
        "tag": release_data.get("tag_name", ""),
        "body": release_data.get("body", "") or "",
    }
