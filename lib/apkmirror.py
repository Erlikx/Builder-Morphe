import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

def sleep_jitter(base=2):
    time.sleep(base + random.uniform(0.5, 2.5))

def download_apk(app_name, config, out_dir):
    base_url = config["am_url"]
    downloaded_file = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        stealth_sync(page)

        # Ağ isteğini yakala (APK linkini bulmak için en garantili yöntem)
        def handle_request(request):
            nonlocal downloaded_file
            if request.url.endswith((".apk", ".apkm")):
                print(f"🔗 İndirme linki yakalandı: {request.url}")
                response = requests.get(request.url, headers={"User-Agent": "Mozilla/5.0"})
                file_name = f"{app_name}-{request.url.split('/')[-1].split('?')[0]}"
                file_path = out_dir / file_name
                with open(file_path, "wb") as f:
                    f.write(response.content)
                downloaded_file = file_path

        page.on("request", handle_request)

        try:
            page.goto(base_url, wait_until="domcontentloaded", timeout=45000)
            sleep_jitter(3)
            
            # Sürüm sayfasını bul
            latest = page.locator("a[href*='-release/']").first
            page.goto(f"https://www.apkmirror.com{latest.get_attribute('href')}", wait_until="domcontentloaded")
            
            # Varyant tablosunda en uygunu tıkla
            page.wait_for_selector(".table-row", timeout=20000)
            for row in page.locator(".table-row").all():
                if any(arch in row.inner_text().lower() for arch in ["arm64-v8a", "universal", "noarch"]):
                    row.locator("a.accent_color").first.click()
                    break
            
            page.wait_for_selector("a.downloadButton", timeout=20000)
            page.locator("a.downloadButton").click()
            
            # İndirme sayfasında biraz bekle, handle_request tetiklensin
            sleep_jitter(10)
            
            if not downloaded_file:
                # Eğer trafikten yakalanamadıysa, eski usul buton ara
                fallback = page.locator("#download-link")
                if fallback.is_visible():
                    fallback.click()
                    sleep_jitter(15)

            return downloaded_file

        except Exception as e:
            print(f"❌ APKMirror Hatası: {e}")
            return None
        finally:
            browser.close()
