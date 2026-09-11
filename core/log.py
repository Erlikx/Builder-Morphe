"""Colorized, GitHub-Actions-aware logging, backed by loguru.

The public surface (header/step/info/download/search/browser/patch/lock/
success/saved/warn/wait/error/colorize_patch_line) is unchanged from before
the loguru migration, so nothing else in the project had to change its
imports or call sites.

Two things loguru buys us over the old print()-based version:
  - `::warning::` / `::error::` GitHub Actions annotations (surfaced in the
    run summary UI, not just buried in the log) now come for free from a
    second sink, instead of a bespoke `_annotate()` helper.
  - Exceptions get loguru's structured traceback rendering - with
    `diagnose=False` explicitly set, since this pipeline's local variables
    routinely include keystore/webhook/token secrets, and `diagnose=True`
    (loguru's default) would print local variable values straight into an
    otherwise-public CI log on any unhandled exception.
"""

import re
import sys

from loguru import logger

from .settings import settings

_COLOR_ENABLED = settings.no_color is None

# ---------------------------------------------------------------------------
# Custom levels for our own "flavor of INFO" categories. Loguru ships
# TRACE/DEBUG/INFO/SUCCESS/WARNING/ERROR/CRITICAL already; everything below
# is project-specific and exists purely for a distinct icon + color, so they
# all sit at severity 21 (just above INFO's 20) - they show up whenever INFO
# does, and would be silenced together with it if a sink's level were ever
# raised above INFO.
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

# Re-skin the built-in levels we reuse so their icons match the old scheme.
logger.level("INFO", color="<blue>", icon="ℹ️")
logger.level("SUCCESS", color="<bold><green>", icon="✅")
logger.level("WARNING", color="<yellow>", icon="⚠️")
logger.level("ERROR", color="<bold><red>", icon="❌")


def _format(record) -> str:
    # HEADER gets the old leading-blank-line treatment to visually separate
    # each app's section in a run that processes more than one.
    if record["level"].name == "HEADER":
        return "\n<level>{level.icon} {message}</level>\n{exception}"
    return "<level>{level.icon}  {message}</level>\n{exception}"


logger.remove()

# androguard also uses loguru internally (it's a shared dependency, and
# loguru's `logger` is a process-wide singleton), so without this its own
# DEBUG/TRACE-level AXML parsing internals (STRING_POOL dumps, raw manifest
# attribute walks, etc. - see get_apk_certificate_fingerprints) would stream
# straight into our sink below and flood the run with noise that has
# nothing to do with this pipeline's own progress reporting.
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

    # WARNING-and-above only (our custom levels all sit below it at 21), and
    # a plain "{message}" format here since GitHub's own UI does the
    # highlighting - we don't want our icon/ANSI wrapping inside it.
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
# OWN lines (ERROR: ..., INFO: Applied: ..., ...) as it runs; this recolors
# them line-by-line as they stream past in real time. These aren't messages
# WE'RE emitting, just a foreign process's stdout being recolored for
# readability, so it stays independent of loguru's record/format machinery -
# plain ANSI wrapping, exactly as before.

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


# The Java patcher (morphe-desktop) already prefixes many of its own lines
# with its own icon (e.g. "✅ INFO: Applied: ...", "⏭️  INFO: Skipping
# disabled: ...", "ℹ️  INFO: Loading patches..."). Every anchored rule above
# (^INFO, ^WARN, ^ERROR, ^INFO:\s*Applied:, ...) was matching against that
# raw text, so it never matched at position 0 - the CLI's own icon was
# sitting there instead of "INFO"/"WARN"/"ERROR". That silently fell
# through to "no rule matched -> return line unchanged", which is why
# "Applied:", "Skipping disabled:" and the plain "INFO:" catch-all lines
# were coming out with no color at all, while the handful of rules that
# don't anchor to the start of the line (e.g. "applying \d+ patches") still
# matched anywhere in the string - just with our icon glued on next to the
# CLI's own one instead of replacing it.
# Deliberately [^A-Za-z]+ rather than [^\w]+: some of the CLI's own icons
# (e.g. "ℹ") are, surprisingly, matched by \w under Python's Unicode regex
# rules, which would leave them un-stripped and defeat this fix for exactly
# the "generic INFO:" line it's meant to cover.
_LEADING_ICON_RE = re.compile(r"^[^A-Za-z]+")


def colorize_patch_line(line: str) -> str:
    stripped = line.rstrip("\n")
    if not stripped.strip():
        return line

    text = _LEADING_ICON_RE.sub("", stripped)

    for pattern, icon, color in _PATCH_LINE_RULES:
        if pattern.search(text):
            return (
                _wrap(f"{icon}{text}", color) + "\n"
                if line.endswith("\n")
                else _wrap(f"{icon}{text}", color)
            )

    return line
