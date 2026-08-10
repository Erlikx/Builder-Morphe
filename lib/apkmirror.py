import asyncio
import logging
import nodriver as uc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def bypass_turnstile(page):
    """
    Cloudflare Turnstile doğrulamasını hedefsiz/ücretsiz yöntemle (nodriver + shadow DOM) geçer.
    """
    try:
        await page.wait(4)
        
        # Turnstile kapsayıcı elementini kontrol et
        cf_wrapper = await page.select("div.cf-turnstile", timeout=5)
        if cf_wrapper:
            logger.info("Turnstile elementi algılandı, tıklanıyor...")
            await cf_wrapper.mouse_move()
            await asyncio.sleep(0.5)
            await cf_wrapper.click()
            await page.wait(3)
            return True

        # Alternatif Challenge iframe tespiti
        iframes = await page.select_all("iframe")
        for iframe in iframes:
            attr_str = " ".join(iframe.attributes) if iframe.attributes else ""
            if "challenges.cloudflare.com" in attr_str:
                logger.info("Cloudflare iframe algılandı, tıklanıyor...")
                await iframe.click()
                await page.wait(3)
                break
    except Exception as e:
        logger.warning(f"Turnstile kontrolü tamamlandı veya gerekmedi: {e}")

async def get_apkmirror_download_link(apkmirror_url: str) -> str:
    """
    APKMirror bağlantısını açar, Turnstile engellerini aşar ve doğrudan APK indirme bağlantısını döndürür.
    """
    logger.info(f"Sayfa açılıyor: {apkmirror_url}")
    
    # Anti-bot tespitini engellemek için headful modda başlatılır (Xvfb ile çalışır)
    browser = await uc.start(
        headless=False,
        browser_args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
            "--window-size=1920,1080",
            "--start-maximized"
        ]
    )

    try:
        page = await browser.get(apkmirror_url)
        await bypass_turnstile(page)

        # Detay sayfasındaki indirme butonuna tıkla
        download_btn = await page.select("a.downloadButton", timeout=10)
        if download_btn:
            logger.info("İndirme butonuna basılıyor...")
            await download_btn.click()
            await page.wait(3)
            await bypass_turnstile(page)

        # Doğrudan indirme bağlantısını (download.php) yakala
        final_link = await page.select("a[rel='nofollow'][href*='download.php']", timeout=10)
        if final_link and final_link.attributes:
            download_url = final_link.attributes.get("href")
            if download_url and not download_url.startswith("http"):
                download_url = "https://www.apkmirror.com" + download_url
            logger.info(f"İndirme bağlantısı başarıyla çekildi: {download_url}")
            return download_url

        return page.url
    finally:
        browser.stop()

if __name__ == "__main__":
    # Test için
    test_url = "https://www.apkmirror.com/"
    asyncio.run(get_apkmirror_download_link(test_url))
