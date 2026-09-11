"""Webhook notifications, sent through apprise.

DISCORD_WEBHOOK_URL / TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID keep working
exactly as before: apprise's Discord plugin accepts a native
`https://discord.com/api/webhooks/...` URL as-is, and a Telegram bot token +
chat id are combined into apprise's `tgram://` scheme. APPRISE_URLS is new:
any additional apprise service URL(s) - Slack, ntfy, Matrix, email, and
everything else at https://github.com/caronc/apprise#supported-notifications
- with no code change ever needed to add one.
"""

import re

import apprise

from . import log
from .settings import settings

_BODY_LIMIT = 2000  # Discord's cap is the tightest of the services we default to


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n... (truncated)"


def _build_apprise() -> apprise.Apprise:
    apobj = apprise.Apprise()

    discord_url = settings.discord_webhook_url.get_secret_value()
    if discord_url:
        apobj.add(discord_url)

    bot_token = settings.telegram_bot_token.get_secret_value()
    chat_id = settings.telegram_chat_id
    if bot_token and chat_id:
        apobj.add(f"tgram://{bot_token}/{chat_id}")

    for url in re.split(r"[\s,]+", settings.apprise_urls.get_secret_value().strip()):
        if url:
            apobj.add(url)

    return apobj


async def notify(text: str) -> None:
    apobj = _build_apprise()
    if not len(apobj):
        return

    try:
        results = await apobj.async_notify(body=_truncate(text, _BODY_LIMIT))
        if not results:
            log.warn("One or more notification targets failed to send (apprise reported failure).")
    except Exception as e:
        log.warn(f"Notification error: {e}")


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
