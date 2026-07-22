import asyncio
import os
import logging
import re
import httpx
import nodriver as uc

class APKMirrorScraper:
    def __init__(self):
        self.browser = None

    async def init_browser(self):
        """
        GitHub Actions / Linux CI ortamında Chrome başlatıcı.
        xvfb-run altında veya headless modda sorunsuz çalışması için
        sandbox=False ayarı ile başlatılır.
        """
        logging.info("🔥 Nodriver Chrome başlatılıyor...")
        try:
            config = uc.Config()
            config.sandbox = False  # Linux CI ortamında root/runner için
            config.headless = True
            
            chrome_binary = "/usr/bin/google-chrome-stable"
            if os.path.exists(chrome_binary):
                config.browser_executable_path = chrome_binary

            self.browser = await uc.start(config=config)
            logging.info("✅ Nodriver Chrome başarıyla başlatıldı.")
        except Exception as e:
            logging.error(f"⚠️ Tarayıcı başlatılamadı: {e}. Fallback (HTTP Direct) moduna geçilecek.")
            self.browser = None

    async def fetch_apk(self, app_name, pkg_name, target_version=None):
        """
        APKMirror üzerinde arama yapıp APK indirme bağlantısını çeker.
        Hem Nodriver hem de HTTP fallback mekanizması içerir.
        """
        url = f"https://www.apkmirror.com/apk/search/?q={pkg_name}"
        logging.info(f"🔎 [TRY] {app_name} aranıyor: {url}")

        download_url = None

        # Yöntem 1: Nodriver ile dinamik tarama
        if self.browser:
            try:
                tab = await self.browser.get(url)
                await asyncio.sleep(3)  # Yüklenme beklemesi

                raw_response = await tab.evaluate("window.__NEXT_DATA__ || window.downloadData || []")

                if isinstance(raw_response, list):
                    item_data = raw_response[0] if len(raw_response) > 0 else {}
                elif isinstance(raw_response, dict):
                    item_data = raw_response
                else:
                    item_data = {}

                if isinstance(item_data, dict):
                    download_url = item_data.get("download_url")

                if not download_url:
                    download_url = await tab.evaluate(
                        "document.querySelector('a.downloadButton')?.href || "
                        "document.querySelector('a[href*=\"/download/\"]')?.href || null"
                    )
            except Exception as e:
                logging.warning(f"Nodriver sorgulama hatası ({app_name}): {e}")

        # Yöntem 2: HTTP Fallback (Eğer Nodriver bağlantı bulamadıysa)
        if not download_url:
            logging.info(f"🌐 [HTTP Fallback] {app_name} için doğrudan HTTP isteği atılıyor...")
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
            try:
                async with httpx.AsyncClient(follow_redirects=True, headers=headers, timeout=15) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        matches = re.findall(r'href="(/apk/[^"]+-download/)"', resp.text)
                        if matches:
                            download_url = "https://www.apkmirror.com" + matches[0]
            except Exception as e:
                logging.error(f"HTTP isteği başarısız ({app_name}): {e}")

        if download_url:
            logging.info(f"🌐 [LİSTE BULUNDU] {app_name}: {download_url}")
            os.makedirs("./downloads", exist_ok=True)
            return f"./downloads/{app_name.lower()}.apk"
        else:
            raise ValueError(f"Uygun indirme bağlantısı oluşturulamadı: {app_name}")

    async def close_browser(self):
        if self.browser:
            try:
                self.browser.stop()
                logging.info("🧹 Tarayıcı oturumu kapatıldı.")
            except Exception:
                pass
