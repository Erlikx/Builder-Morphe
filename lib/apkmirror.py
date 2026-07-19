import time
import random
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

def sleep_jitter(base=2):
    time.sleep(base + random.uniform(0.5, 2.5))

def download_apk(app_name, config, out_dir, target_version=None):
    base_url = config["am_url"]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        stealth_sync(page)
        
        try:
            # 1. Sürüm sayfasını bul
            page.goto(base_url, wait_until="domcontentloaded", timeout=45000)
            release_url = None
            if target_version:
                version_slug = target_version.replace(".", "-")
                # Sürüm numarasını içeren linki doğrudan hedefle
                target = page.locator(f"a[href*='-{version_slug}-']").first
                if target.count() > 0:
                    release_url = f"https://www.apkmirror.com{target.get_attribute('href')}"
            
            if not release_url:
                latest = page.locator("a[href*='-release/']").first
                release_url = f"https://www.apkmirror.com{latest.get_attribute('href')}"
            
            page.goto(release_url, wait_until="domcontentloaded", timeout=45000)
            
            # 2. Mimariyi seç
            page.wait_for_selector(".table-row", timeout=20000)
            rows = page.locator(".table-row").all()
            variant_path = None
            for row in rows:
                if any(x in row.inner_text().lower() for x in ["arm64-v8a", "universal", "noarch"]):
                    variant_path = row.locator("a.accent_color").first.get_attribute("href")
                    break
            
            # 3. Varyant sayfasına git
            page.goto(f"https://www.apkmirror.com{variant_path}", wait_until="domcontentloaded", timeout=45000)
            
            # 4. "DOWNLOAD" butonuna tıkladığında oluşan linki bul ve doğrudan çek
            page.wait_for_selector("a.downloadButton", timeout=20000)
            dl_page_url = f"https://www.apkmirror.com{page.locator('a.downloadButton').get_attribute('href')}"
            
            page.goto(dl_page_url, wait_until="domcontentloaded", timeout=45000)
            
            # 5. İndirme linkinin HTML'de oluşmasını bekle
            page.wait_for_selector("#download-link", timeout=20000)
            direct_link = page.locator("#download-link").get_attribute("href")
            
            print(f"🔗 Yakalanan İndirme Linki: {direct_link}")
            
            # 6. Tarayıcıyı beklemeden requests ile indir
            r = requests.get(direct_link, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
            r.raise_for_status()
            
            file_path = out_dir / f"{app_name}.apk"
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"📦 BAŞARILI: {file_path}")
            return file_path
            
        except Exception as e:
            print(f"❌ İndirme Hatası: {e}")
            return None
        finally:
            browser.close()
