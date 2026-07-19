import os
import requests
from .http import download_file_pro

APP_TAGS = {
    "instagram": "instagram", "speedtest": "Speedtest", "pydroid3": "Pydroid3",
    "github": "github", "niagara-launcher": "NiagaraLauncher", "solid-explorer": "SolidExplorer",
    "gboard": "Gboard", "wps-office": "WPSOffice", "smart-launcher": "SmartLauncher", "brave": "brave"
}

def download_apk(version: str, app_name: str) -> str:
    tag = APP_TAGS.get(app_name)
    if not tag:
        raise Exception("Tag not found")
    url = f"https://api.github.com/repos/fuckpdf/Depo/releases/tags/{tag}"
    res = requests.get(url, headers={"User-Agent": "python"})
    if not res.ok:
        raise Exception("GitHub API Error")
    data = res.json()
    asset = next((a for a in data.get("assets", []) if a["name"].endswith(".apk") or a["name"].endswith(".apkm")), None)
    if not asset:
        raise Exception("APK not found")
    out_dir = os.path.abspath("downloads")
    os.makedirs(out_dir, exist_ok=True)
    file_path = os.path.join(out_dir, asset["name"])
    download_file_pro(asset["browser_download_url"], file_path)
    return file_path
