import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

def sleep_jitter(base=2):
    time.sleep(base + random.uniform(0.5, 2.5))

def download_apk(app_name, config, out_dir):
    base_url = config["am_url"]
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0 Safari/537.36",
            accept_downloads=True,
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        stealth_sync(page)
        
        try:
            print(f"🌐 Liste: {base_url}")
            page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
            sleep_jitter(3)
            
            latest_release = page.locator("a[href*='-release/']").first
            release_url = f"https://www.apkmirror.com{latest_release.get_attribute('href')}"
            
            page.goto(release_url, wait_until="domcontentloaded", timeout=30000)
            sleep_jitter(2)
            
            page.wait_for_selector(".table-row", timeout=15000)
            rows = page.locator(".table-row").all()
            
            variant_url = None
            for row in rows:
                text = row.inner_text().lower()
                if "arm64-v8a" in text or "universal" in text or "noarch" in text:
                    link = row.locator("a.accent_color").first
                    if link:
                        variant_url = f"https://www.apkmirror.com{link.get_attribute('href')}"
                        break
                        
            if not variant_url:
                raise Exception("Uygun mimari bulunamadı.")
                
            print(f"➡️ Varyant: {variant_url}")
            page.goto(variant_url, wait_until="domcontentloaded", timeout=30000)
            sleep_jitter(2)
            
            page.wait_for_selector("a.downloadButton", timeout=15000)
            dl_href = page.locator("a.downloadButton").get_attribute("href")
            dl_url = f"https://www.apkmirror.com{dl_href}"
            
            print(f"⬇️ İndirme başlatılıyor...")
            page.goto(dl_url, wait_until="domcontentloaded", timeout=30000)
            
            with page.expect_download(timeout=60000) as dl_info:
                fallback = page.locator("#download-link")
                if fallback.is_visible():
                    fallback.click()
            
            download = dl_info.value
            file_name = f"{app_name}-{download.suggested_filename}"
            file_path = out_dir / file_name
            download.save_as(file_path)
            print(f"📦 BAŞARILI: {file_path}")
            return file_path
            
        except Exception as e:
            print(f"❌ APKMirror Hatası: {str(e)}")
            return None
        finally:
            browser.close()
