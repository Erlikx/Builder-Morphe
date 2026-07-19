import re
from typing import Optional


def extract_versions(output: str) -> list[dict]:
    results = []
    lines = output.splitlines()
    in_section = False

    for line in lines:
        trimmed = line.strip()
        if trimmed.startswith("Most common compatible versions"):
            in_section = True
            continue
        if in_section and not trimmed:
            break
        if in_section:
            match = re.match(
                r"^(\d+\.\d+\.\d+(?:-[a-zA-Z]+\.\d+)?)\s+\((\d+)\s+patches\)",
                trimmed,
            )
            if match:
                results.append({"version": match.group(1), "patches": int(match.group(2))})

    if not results:
        fallback = re.findall(r"\d+\.\d+\.\d+(?:-[a-zA-Z]+\.\d+)?", output)
        results = [{"version": v, "patches": 0} for v in fallback]

    return results


def _version_core(version: str) -> tuple[int, ...]:
    core = version.split("-")[0]
    return tuple(int(x) for x in core.split("."))


def pick_latest_version(lst: list[dict]) -> Optional[str]:
    if not lst:
        return None
    sorted_lst = sorted(
        lst,
        key=lambda x: (x["patches"], _version_core(x["version"])),
        reverse=True,
    )
    return sorted_lst[0]["version"]


def to_apkmirror_version(version: str) -> str:
    return version.replace(".", "-")
