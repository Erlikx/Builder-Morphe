import re

def extract_youtube_versions(output):
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
            match = re.match(r'^(\d+\.\d+\.\d+(?:-[a-zA-Z]+\.\d+)?)\s+\((\d+)\s+patches\)', trimmed)
            if match:
                results.append({
                    "version": match.group(1),
                    "patches": int(match.group(2))
                })

    if not results:
        versions = re.findall(r'\d+\.\d+\.\d+(?:-[a-zA-Z]+\.\d+)?', output)
        return [{"version": v, "patches": 0} for v in versions]

    return results

def version_core(version):
    return version.split("-")[0]

def pick_latest_version(version_list):
    if not version_list:
        return None

    sorted_list = sorted(version_list, key=lambda x: (
        -x["patches"],
        *[int(p) for p in version_core(x["version"]).split(".")]
    ))

    return sorted_list[0]["version"]

def to_apk_mirror_version(version):
    return version.replace(".", "-")
