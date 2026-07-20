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
            match = re.match(r"^(\d+\.\d+\.\d+(?:-[a-zA-Z]+\.\d+)?)\s+\((\d+)\s+patches\)", trimmed)
            if match:
                results.append({
                    "version": match.group(1),
                    "patches": int(match.group(2))
                })

    if not results:
        fallback = re.findall(r"\d+\.\d+\.\d+(?:-[a-zA-Z]+\.\d+)?", output)
        return [{"version": v, "patches": 0} for v in fallback]

    return results

def version_core(version: str) -> str:
    return version.split("-")[0]

def pick_latest_version(version_list: list[dict]) -> str | None:
    if not version_list:
        return None

    def sort_key(item):
        core = version_core(item["version"])
        parts = []
        for p in core.split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        return (item["patches"], parts)

    sorted_list = sorted(version_list, key=sort_key, reverse=True)
    return sorted_list[0]["version"]

def to_apkmirror_version(version: str) -> str:
    return version.replace(".", "-").replace(" ", "-")
