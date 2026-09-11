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


class _C:
    RESET = "\033[0m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def _wrap(text: str, *codes: str) -> str:
    if not _COLOR_ENABLED:
        return text
    return f"{''.join(codes)}{text}{_C.RESET}"


_PATCH_LINE_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"^ERROR", re.IGNORECASE), "❌ ", _C.RED),
    (re.compile(r"^WARN", re.IGNORECASE), "⚠️  ", _C.YELLOW),
    (re.compile(r"applying \d+ patches", re.IGNORECASE), "🩹 ", _C.CYAN),
    (re.compile(r"executing patches", re.IGNORECASE), "⚙️  ", _C.CYAN),
    (re.compile(r"^INFO:\s*Applied:", re.IGNORECASE), "✅ ", _C.GREEN),
    (re.compile(r"^INFO:\s*Saved to", re.IGNORECASE), "💾 ", _C.GREEN),
    (re.compile(r"compiling patched dex", re.IGNORECASE), "🛠️  ", _C.CYAN),
    (re.compile(r"stripping libs|stripped \d+ lib", re.IGNORECASE), "✂️  ", _C.CYAN),
    (re.compile(r"aligning apk", re.IGNORECASE), "📐 ", _C.CYAN),
    (re.compile(r"signing apk", re.IGNORECASE), "🔏 ", _C.CYAN),
    (re.compile(r"purged .*temp files", re.IGNORECASE), "🧹 ", _C.GRAY),
    (re.compile(r"^\S[\w .\-']*: patched \d+ ", re.IGNORECASE), "🎨 ", _C.GREEN),
    (re.compile(r"^INFO:\s*Skipping disabled", re.IGNORECASE), "⏭️  ", _C.GRAY),
    (re.compile(r"^INFO:", re.IGNORECASE), "ℹ️  ", _C.BLUE),
]

_LEADING_ICON_RE = re.compile(r"^[^A-Za-z]+")


def colorize_patch_line(line: str) -> str:
    stripped = line.rstrip("\n")
    if not stripped.strip():
        return line

    text = _LEADING_ICON_RE.sub("", stripped)

    for pattern, icon, color in _PATCH_LINE_RULES:
        if pattern.search(text):
            return _wrap(f"{icon}{text}", color) + "\n" if line.endswith("\n") else _wrap(f"{icon}{text}", color)

    return line
