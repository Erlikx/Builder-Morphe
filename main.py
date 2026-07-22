import asyncio
import os
import logging
import nodriver as uc

class APKMirrorScraper:
    def __init__(self):
        self.browser = None

    async def init_browser(self):
        """
        [DÜZELTME] Nodriver Chrome Başlatma (GitHub Runner Uyumlu).
        Nodriver kütüphanesinde '--no-sandbox' add_argument ile verilemez.
        Doğrudan Config.sandbox = False ve Config.headless = True kullanılır.
        """
        logging.info("🔥 Nodriver Chrome başlatılıyor (sandbox=False)...")
        
        config = uc.Config()
        config.sandbox = False  # Root runner için sandbox'ı güvenli şekilde kapatır
        config.headless = True
        
        chrome_binary = "/usr/bin/google-chrome-stable"
        if os.path.exists(chrome_binary):
            config.browser_executable_path = chrome_binary

        self.browser = await uc.start(config=config)
        logging.info("✅ Nodriver Chrome başarıyla başlatıldı.")

    async def fetch_apk(self, app_name, pkg_name, target_version=None):
        """
        [DÜZELTME] 'list object has no attribute get' Hatasının Çözümü.
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
