import re
import sys

from loguru import logger

from .settings import settings

_COLOR_ENABLED = settings.no_color is None

for _name, _color, _icon in [
    ("HEADER", "<bold><cyan>", "▶"),
    ("STEP", "<cyan>", "🔧"),
    ("DOWNLOAD", "<magenta>", "📦"),
    ("SEARCH", "<blue>", "🔍"),
    ("BROWSER", "<blue>", "🌐"),
    ("PATCH", "<cyan>", "🩹"),
    ("LOCK", "<blue>", "🔐"),
    ("SAVED", "<green>", "💾"),
    ("WAIT", "<yellow>", "⏳"),
    # Below: classifications for morphe-desktop's own per-line passthrough
    # output (see patch_line()) - not messages we emit ourselves.
    ("APPLIED", "<cyan>", "✅"),
    ("SKIPPED", "<red>", "⏭️"),
]:
    logger.level(_name, no=21, color=_color, icon=_icon)

logger.level("INFO", color="<blue>", icon="ℹ️")
logger.level("SUCCESS", color="<bold><green>", icon="✅")
logger.level("WARNING", color="<yellow>", icon="⚠️")
logger.level("ERROR", color="<bold><red>", icon="❌")


def _format(record) -> str:
    if record["level"].name == "HEADER":
        return "\n<level>{level.icon} {message}</level>\n{exception}"
    return "<level>{level.icon}  {message}</level>\n{exception}"


logger.remove()
logger.disable("androguard")

logger.add(
    sys.stdout,
    level="TRACE",
    format=_format,
    colorize=_COLOR_ENABLED,
    backtrace=True,
    diagnose=False,
)

if settings.github_actions:

    def _escape_workflow_command(text: str) -> str:
        return text.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")

    def _github_annotation(message) -> None:
        record = message.record
        gha_level = "error" if record["level"].name == "ERROR" else "warning"
        sys.stdout.write(f"::{gha_level}::{_escape_workflow_command(record['message'])}\n")

    logger.add(_github_annotation, level="WARNING", format="{message}")


def header(msg: str) -> None:
    logger.log("HEADER", msg)


def step(msg: str) -> None:
    logger.log("STEP", msg)


def info(msg: str) -> None:
    logger.info(msg)


def download(msg: str) -> None:
    logger.log("DOWNLOAD", msg)


def search(msg: str) -> None:
    logger.log("SEARCH", msg)


def browser(msg: str) -> None:
    logger.log("BROWSER", msg)


def patch(msg: str) -> None:
    logger.log("PATCH", msg)


def lock(msg: str) -> None:
    logger.log("LOCK", msg)


def success(msg: str) -> None:
    logger.success(msg)


def saved(msg: str) -> None:
    logger.log("SAVED", msg)


def warn(msg: str) -> None:
    logger.warning(msg)


def wait(msg: str) -> None:
    logger.log("WAIT", msg)


def error(msg: str) -> None:
    logger.error(msg)


# ---------------------------------------------------------------------------
# Patch-tool output passthrough. The Java patcher (morphe-desktop) prints its
# OWN lines (ERROR: ..., INFO: Applied: ..., ...) as it runs. patch_line()
# classifies each one and re-emits it through the SAME loguru sink as every
# other message in this module (header/step/download/... above), instead of
# hand-rolled raw \033[..m ANSI wrapping. The hand-rolled version wasn't
# rendering reliably in this project's GitHub Actions log viewer - every
# category came out uncolored, not just the ones with an anchoring bug -
# while loguru's own sink (proven working for step/download/success/etc.)
# renders fine there, so this routes through that instead of debugging the
# raw-ANSI path further.

# The CLI already prefixes many of its own lines with its own icon (e.g.
# "✅ INFO: Applied: ...", "⏭️  INFO: Skipping disabled: ...", "ℹ️  INFO:
# Loading patches..."). Stripped here so the rules below (which look for
# "INFO:", "WARN", "ERROR" at the start of the text) see the real text
# instead of that icon, and so the final line carries exactly one (ours)
# icon instead of two. Deliberately [^A-Za-z]+ rather than [^\w]+: some of
# the CLI's icons (e.g. "ℹ") are, surprisingly, matched by \w under
# Python's Unicode regex rules, which would leave them un-stripped.
_LEADING_ICON_RE = re.compile(r"^[^A-Za-z]+")

_PATCH_LINE_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^ERROR", re.IGNORECASE), "ERROR"),
    (re.compile(r"^WARN", re.IGNORECASE), "WARNING"),
    (re.compile(r"applying \d+ patches", re.IGNORECASE), "PATCH"),
    (re.compile(r"executing patches", re.IGNORECASE), "PATCH"),
    (re.compile(r"^INFO:\s*Applied:", re.IGNORECASE), "APPLIED"),
    (re.compile(r"^INFO:\s*Saved to", re.IGNORECASE), "SAVED"),
    (re.compile(r"compiling patched dex", re.IGNORECASE), "PATCH"),
    (re.compile(r"stripping libs|stripped \d+ lib", re.IGNORECASE), "PATCH"),
    (re.compile(r"aligning apk", re.IGNORECASE), "PATCH"),
    (re.compile(r"signing apk", re.IGNORECASE), "PATCH"),
    (re.compile(r"purged .*temp files", re.IGNORECASE), "STEP"),
    (re.compile(r"^\S[\w .\-']*: patched \d+ ", re.IGNORECASE), "APPLIED"),
    (re.compile(r"^INFO:\s*Skipping disabled", re.IGNORECASE), "SKIPPED"),
    (re.compile(r"^INFO:", re.IGNORECASE), "INFO"),
]


def patch_line(line: str) -> None:
    stripped = line.rstrip("\n")
    if not stripped.strip():
        return

    text = _LEADING_ICON_RE.sub("", stripped)

    for pattern, level in _PATCH_LINE_RULES:
        if pattern.search(text):
            logger.log(level, text)
            return

    logger.log("INFO", text)
