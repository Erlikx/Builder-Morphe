import os
import re

_COLOR_ENABLED = os.environ.get("NO_COLOR") is None


class _C:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    GRAY = "\033[90m"


def _wrap(text: str, *codes: str) -> str:
    if not _COLOR_ENABLED:
        return text
    return f"{''.join(codes)}{text}{_C.RESET}"


def header(msg: str) -> None:
    print(_wrap(f"\n▶ {msg}", _C.BOLD, _C.CYAN))


def step(msg: str) -> None:
    print(_wrap(f"🔧 {msg}", _C.CYAN))


def info(msg: str) -> None:
    print(_wrap(f"ℹ️  {msg}", _C.BLUE))


def download(msg: str) -> None:
    print(_wrap(f"📦 {msg}", _C.MAGENTA))


def search(msg: str) -> None:
    print(_wrap(f"🔍 {msg}", _C.BLUE))


def browser(msg: str) -> None:
    print(_wrap(f"🌐 {msg}", _C.BLUE))


def patch(msg: str) -> None:
    print(_wrap(f"🩹 {msg}", _C.CYAN))


def lock(msg: str) -> None:
    print(_wrap(f"🔐 {msg}", _C.BLUE))


def success(msg: str) -> None:
    print(_wrap(f"✅ {msg}", _C.GREEN, _C.BOLD))


def saved(msg: str) -> None:
    print(_wrap(f"💾 {msg}", _C.GREEN))


def warn(msg: str) -> None:
    print(_wrap(f"⚠️  {msg}", _C.YELLOW))


def wait(msg: str) -> None:
    print(_wrap(f"⏳ {msg}", _C.YELLOW))


def error(msg: str) -> None:
    print(_wrap(f"❌ {msg}", _C.RED, _C.BOLD))



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


def colorize_patch_line(line: str) -> str:
    stripped = line.rstrip("\n")
    if not stripped.strip():
        return line

    for pattern, icon, color in _PATCH_LINE_RULES:
        if pattern.search(stripped):
            return _wrap(f"{icon}{stripped}", color) + "\n" if line.endswith("\n") else _wrap(f"{icon}{stripped}", color)

    return line
