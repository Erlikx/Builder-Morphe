import os

from . import log
from .http import new_session

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

_DISCORD_LIMIT = 2000
_TELEGRAM_LIMIT = 4096


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n... (truncated)"


async def _send_discord(text: str) -> None:
    async with new_session(timeout=15) as client:
        res = await client.post(DISCORD_WEBHOOK_URL, json={"content": _truncate(text, _DISCORD_LIMIT)})
        if res.status_code >= 400:
            log.warn(f"Discord notification failed: HTTP {res.status_code}")


async def _send_telegram(text: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with new_session(timeout=15) as client:
        res = await client.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": _truncate(text, _TELEGRAM_LIMIT),
                "disable_web_page_preview": True,
            },
        )
        if res.status_code >= 400:
            log.warn(f"Telegram notification failed: HTTP {res.status_code}")


async def notify(text: str) -> None:
    if DISCORD_WEBHOOK_URL:
        try:
            await _send_discord(text)
        except Exception as e:
            log.warn(f"Discord notification error: {e}")

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        try:
            await _send_telegram(text)
        except Exception as e:
            log.warn(f"Telegram notification error: {e}")


def format_summary(release_name: str, release_url: str, matched: list[dict], failed_keys: list[str]) -> str:
    lines = [f"✅ {release_name}", "", f"{len(matched)} app(s) patched:"]
    lines += [f"  • {apk['display_name']} — {apk['version']}" for apk in matched]

    if failed_keys:
        lines += ["", f"⚠️ {len(failed_keys)} app(s) failed or produced no APK:"]
        lines += [f"  • {key}" for key in failed_keys]

    lines += ["", release_url]
    return "\n".join(lines)


def format_all_failed(release_name: str, failed_keys: list[str]) -> str:
    lines = [f"❌ {release_name} — no apps were patched successfully this run."]
    if failed_keys:
        lines += ["", f"{len(failed_keys)} app(s) failed or produced no APK:"]
        lines += [f"  • {key}" for key in failed_keys]
    lines += ["", "Check the Actions run log for details."]
    return "\n".join(lines)
