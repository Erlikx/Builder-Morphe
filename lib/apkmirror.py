import os
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from .versions import to_apkmirror_version

APP_SITES = {
    "youtube": {"org": "google-inc", "slug": "youtube"},
    "youtube-music": {"org": "google-inc", "slug": "youtube-music"},
    "reddit": {"org": "reddit-inc", "slug": "reddit"},
    "twitter": {"org": "x-corp", "slug": "twitter", "releaseSlug": "x"},
    "instagram": {"org": "instagram", "slug": "instagram"},
    "niagara-launcher": {"org": "mellowdrop-studio", "slug": "niagara-launcher"}
}

def get_latest_listing(app_name: str):
    app_config = APP_SITES.get(app_name)
    if not app_config:
        raise Exception("Unknown appName")
    
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # ÇÖZÜM BURADA: Sürümü 150 olarak sabitliyoruz
    driver = uc.Chrome(options=options, version_main=150)
    
    try:
        driver.get(f"https://www.apkmirror.com/apk/{app_config['org']}/{app_config['slug']}/")
        time.sleep(5)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        for link in soup.find_all("a", href=True):
            if "-release/" in link["href"]:
                row = link.find_parent(["div", "li", "tr"])
                text = row.get_text() if row else link.get_text()
                import re
                match = re.search(r'\d+(?:\.\d+)+', text)
                if match:
                    return {"version": match.group(0), "href": link["href"]}
    finally:
        driver.quit()
    return None

def download_apk(version: str, app_name: str, force_build: str = None) -> str:
    app_config = APP_SITES.get(app_name)
    version_slug = to_apkmirror_version(version)
    name_part = app_config.get("releaseSlug", app_config["slug"])
    folder_url = f"https://www.apkmirror.com/apk/{app_config['org']}/{app_config['slug']}"
    
    out_dir = os.path.abspath("downloads")
    os.makedirs(out_dir, exist_ok=True)
    
    options = uc.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    prefs = {
        "download.default_directory": out_dir,
        "download.prompt_for_download": False,
        "safebrowsing.enabled": True
    }
    options.add_experimental_option("prefs", prefs)
    
    # ÇÖZÜM BURADA: Sürümü 150 olarak sabitliyoruz
    driver = uc.Chrome(options=options, version_main=150)
    try:
        candidates = [
            f"{folder_url}/{name_part}-{version_slug}-release/",
            f"{folder_url}/{name_part}-{version_slug}-release-0-release/"
        ]
        
        list_url = None
        for candidate in candidates:
            driver.get(candidate)
            time.sleep(4)
            if "404" not in driver.title and driver.find_elements(uc.By.CSS_SELECTOR, ".table-row"):
                list_url = candidate
                break
        
        if not list_url:
            driver.get(f"{folder_url}/")
            time.sleep(5)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            for link in soup.find_all("a", href=True):
                if f"-{version_slug}-" in link["href"] and "-release/" in link["href"]:
                    list_url = urljoin("https://www.apkmirror.com", link["href"])
                    break
                    
        if not list_url:
            raise Exception("No APKMirror release page found")

        driver.get(list_url)
        time.sleep(5)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        variant_url = None
        for row in soup.find_all(class_="table-row"):
            cells = row.find_all(class_="table-cell")
            if len(cells) < 4:
                continue
            link = cells[0].find("a", class_="accent_color")
            if not link:
                continue
            if force_build and force_build not in cells[0].get_text():
                continue
            badge = cells[0].find(class_="apkm-badge")
            is_bundle = False
            if badge:
                b_text = badge.get_text().upper()
                is_bundle = "BUNDLE" in b_text or "PAKET" in b_text
            if app_name == "instagram" and not is_bundle:
                continue
            arch_text = cells[1].get_text().strip().lower()
            dpi_text = cells[3].get_text().strip().lower()
            
            is_target_arch = arch_text == "" or "universal" in arch_text or "arm64-v8a" in arch_text
            import re
            is_target_dpi = dpi_text == "" or "nodpi" in dpi_text or "anydpi" in dpi_text or bool(re.search(r'\d+-640dpi', dpi_text))
            
            if is_target_arch and is_target_dpi:
                variant_url = urljoin("https://www.apkmirror.com", link["href"])
                break
        
        if not variant_url:
            raise Exception("No matching variant found")

        driver.get(variant_url)
        time.sleep(5)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        dl_btn = soup.find("a", class_="downloadButton")
        if not dl_btn:
            raise Exception("Download button not found")
            
        download_page_url = urljoin("https://www.apkmirror.com", dl_btn["href"])
        driver.get(download_page_url)
        time.sleep(15)
        
        downloaded_files = [f for f in os.listdir(out_dir) if f.endswith(".apk")]
        if downloaded_files:
            return os.path.join(out_dir, downloaded_files[0])
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        fallback_link = soup.find("a", id="download-link")
        if fallback_link:
            fallback_url = urljoin("https://www.apkmirror.com", fallback_link["href"])
            import requests
            res = requests.get(fallback_url, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
            file_name = res.url.split("/")[-1]
            if not file_name.endswith(".apk"):
                file_name = f"{app_name}.apk"
            file_path = os.path.join(out_dir, file_name)
            with open(file_path, 'wb') as f:
                f.write(res.content)
            return file_path
            
        raise Exception("Download failed")
    finally:
        driver.quit()
