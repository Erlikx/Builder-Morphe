import os
from playwright.sync_api import sync_playwright
from .versions import to_apkmirror_version

def download_apk(version: str, app_name: str, force_build: str = None) -> str:
    out_dir = os.path.abspath("downloads")
    os.makedirs(out_dir, exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # APKMirror linki oluşturma mantığı...
        # (Buraya daha önce verdiğim link mantığını uygulayacağız)
        # ÖNEMLİ: İndirme işleminde page.expect_download() kullanacağız.
        
        with page.expect_download() as download_info:
            page.click("a.downloadButton")
        download = download_info.value
        file_path = os.path.join(out_dir, download.suggested_filename)
        download.save_as(file_path)
        
        browser.close()
        return file_path
