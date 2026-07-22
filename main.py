import asyncio
import os
import sys
import pathlib
import logging
from lib.apkmirror import APKMirrorScraper
from lib.patcher import MorphePatchEngine

# Logging Yapılandırması
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Performans İçin Paralellik Limiti (Max 3 Eşzamanlı İndirme & Yamalama)
CONCURRENCY_LIMIT = 3
SEMAPHORE = asyncio.Semaphore(CONCURRENCY_LIMIT)

TARGET_APPS = [
    {"name": "YOUTUBE", "pkg": "com.google.android.youtube", "patch_mpp": "patches-3.8.0-dev.5.mpp"},
    {"name": "YOUTUBE-MUSIC", "pkg": "com.google.android.apps.youtube.music", "patch_mpp": "patches-3.8.0-dev.5.mpp"},
    {"name": "REDDIT", "pkg": "com.reddit.frontpage", "patch_mpp": "patches-3.8.0-dev.5.mpp"},
    {"name": "TWITTER", "pkg": "com.twitter.android", "patch_mpp": "patches-3.8.0-dev.5.mpp"},
    {"name": "INSTAGRAM", "pkg": "com.instagram.android", "patch_mpp": "patches-3.8.0-dev.5.mpp"},
    {"name": "SPEEDTEST", "pkg": "org.zwanoo.android.speedtest", "patch_mpp": "patches-1.14.0.mpp"},
    {"name": "BRAVE", "pkg": "com.brave.browser", "patch_mpp": "patches-3.8.0-dev.5.mpp"},
    {"name": "NIAGARA-LAUNCHER", "pkg": "bitpit.launcher", "patch_mpp": "patches-3.8.0-dev.5.mpp"},
    {"name": "WPS-OFFICE", "pkg": "cn.wps.moffice_eng", "target_ver": "18.24", "patch_mpp": "patches-1.40.0-dev.2.mpp"}
]

async def process_app(app_info, scraper, patch_engine):
    async with SEMAPHORE:
        app_name = app_info["name"]
        logging.info(f"📦 [BAŞLATILDI] {app_name} işleniyor...")
        
        try:
            # 1. APK İndirme (Düzeltilmiş Tip Kontrollü Scraper)
            target_version = app_info.get("target_ver")
            apk_path = await scraper.fetch_apk(app_name, app_info["pkg"], target_version)
            
            if not apk_path or not os.path.exists(apk_path):
                logging.error(f"❌ {app_name} APK indirilemedi, atlanıyor.")
                return False

            # 2. Morphe ile Yamalama & İmzalama
            patched_apk = await patch_engine.apply_patches(
                apk_path=apk_path,
                patch_file=app_info["patch_mpp"],
                arch="arm64-v8a"
            )

            logging.info(f"✅ [BAŞARILI] {app_name} yamalandı: {patched_apk}")
            return True

        except Exception as e:
            logging.error(f"❌ {app_name} işlenirken hata oluştu: {e}")
            return False

async def main():
    logging.info("🚀 Builder-Morphe Optimize Edilmiş İşlem Başlatılıyor...")
    
    scraper = APKMirrorScraper()
    patch_engine = MorphePatchEngine()

    try:
        # Paylaşılan Nodriver Chrome Oturumunu Güvenli Başlat
        await scraper.init_browser()

        # Tüm Uygulamaları Paralel Olarak Çalıştır (Asyncio Gather)
        tasks = [process_app(app, scraper, patch_engine) for app in TARGET_APPS]
        results = await asyncio.gather(*tasks)

        success_count = sum(1 for r in results if r)
        total_count = len(results)
        logging.info(f"🎉 İşlem Tamamlandı: {success_count}/{total_count} uygulama başarıyla derlendi!")

    finally:
        await scraper.close_browser()

if __name__ == "__main__":
    asyncio.run(main())
