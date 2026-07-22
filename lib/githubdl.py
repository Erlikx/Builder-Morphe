from pathlib import Path

import httpx

APP_TAGS = {
    "instagram": "instagram",
    "speedtest": "Speedtest",
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
