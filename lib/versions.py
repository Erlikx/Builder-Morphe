import re


def extract_youtube_versions(output: str) -> list[dict]:
    results = []
    lines = output.split("\n")
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
                r"^(\d+\.\d+\.\d+(?:-[a-zA-Z]+(?:\.\d+)?)?)\s+\((\d+)\s+patches\)",
                trimmed,
            )
            if match:
                results.append({"version": match.group(1), "patches": int(match.group(2))})

    if not results:
        fallback = re.findall(r"\d+\.\d+\.\d+(?:-[a-zA-Z]+(?:\.\d+)?)?", output)
        return [{"version": v, "patches": 0} for v in fallback]

    return results


def _version_core(version: str) -> str:
    return version.split("-")[0]


def pick_latest_version(versions: list[dict]) -> str | None:
    if not versions:
        return None

    def sort_key(item: dict):
        parts = _version_core(item["version"]).split(".")
        try:
            core = tuple(int(p) for p in parts[:3])
        except ValueError:
            core = (0, 0, 0)
        return (item["patches"], core)

    best = max(versions, key=sort_key)
    return best["version"]


def to_apkmirror_version(version: str) -> str:
    return version.replace(".", "-")
