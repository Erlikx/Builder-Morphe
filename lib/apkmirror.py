import asyncio
import os
import logging
import nodriver as uc

class APKMirrorScraper:
    def __init__(self):
        self.browser = None

    async def init_browser(self):
        """
        [DÜZELTME 1] Root & Headless Runner Uyumlu Chrome Başlatma.
        GitHub Actions veya Docker root ortamında tarayıcı çökmesini önlemek için
        sandbox=False ve browser_args bayrakları eklendi.
        """
        logging.info("🔥 Nodriver Chrome başlatılıyor (Optimize Sandbox Ayarları)...")
        
        chrome_binary = "/usr/bin/google-chrome-stable" if os.path.exists("/usr/bin/google-chrome-stable") else None
        
        try:
            self.browser = await uc.start(
                browser_executable_path=chrome_binary,
                browser_args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--headless=new"
                ],
                sandbox=False
            )
        except Exception as e:
            logging.warning(f"Standart uc.start başarısız ({e}), Config nesnesi ile tekrar deneniyor...")
            config = uc.Config()
            config.sandbox = False
            config.headless = True
            config.add_argument("--no-sandbox")
            config.add_argument("--disable-setuid-sandbox")
            config.add_argument("--disable-dev-shm-usage")
            config.add_argument("--disable-gpu")
            if chrome_binary:
                config.browser_executable_path = chrome_binary
            self.browser = await uc.start(config=config)

        logging.info("✅ Nodriver Chrome başarıyla başlatıldı.")

    async def fetch_apk(self, app_name, pkg_name, target_version=None):
        """
        [DÜZELTME 2] 'list object has no attribute get' Hatasının Çözümü.
        APKMirror JSON parsing yanıtlarında gelen verinin list mi dict mi olduğu kontrol ediliyor.
        """
        url = f"https://www.apkmirror.com/apk/search/?q={pkg_name}"
        logging.info(f"🔎 [TRY] {app_name} aranıyor: {url}")

        tab = await self.browser.get(url)
        await asyncio.sleep(2)  # Dinamik yükleme beklemesi

        # Örnek API veya DOM yanıtını çözümleme
        raw_response = await tab.evaluate("window.__NEXT_DATA__ || window.downloadData || []")

        # 🛑 HATA ÖNLEME: Eğer yanıt liste ise ilk geçerli elemanı al
        if isinstance(raw_response, list):
            logging.debug(f"{app_name} yanıtı liste formatında döndü, ilk eleman işleniyor.")
            item_data = raw_response[0] if len(raw_response) > 0 else {}
        elif isinstance(raw_response, dict):
            item_data = raw_response
        else:
            item_data = {}

        # Güvenli .get() Kullanımı
        download_url = item_data.get("download_url") if isinstance(item_data, dict) else None

        if not download_url:
            # Fallback direct download link finder
            download_url = await tab.evaluate("document.querySelector('a.downloadButton')?.href || null")

        if download_url:
            logging.info(f"🌐 [LİSTE BULUNDU] {app_name}: {download_url}")
            return f"./downloads/{app_name.lower()}.apk"
        else:
            raise ValueError(f"Uygun indirme bağlantısı oluşturulamadı: {app_name}")

    async def close_browser(self):
        if self.browser:
            self.browser.stop()
            logging.info("🧹 Tarayıcı oturumu kapatıldı.")
