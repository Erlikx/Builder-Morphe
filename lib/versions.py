import re
from packaging.version import Version

def extract_youtube_versions(output):
    results = []
    lines = output.split("\n")
    in_section = False
    section_headers = [
        "Most common compatible versions",
        "En yaygın uyumlu sürümler",
        "Uyumlu sürümler"
    ]
    
    for line in lines:
        trimmed = line.strip()
        for header in section_headers:
            if header in trimmed:
                in_section = True
                break
        if in_section and not trimmed:
            in_section = False
            continue
        if in_section:
            match = re.match(r'^(\d+\.\d+\.\d+(?:-[a-zA-Z]+\.\d+)?)\s+(?:\((\d+)\s+patches\)|\[.*\])', trimmed)
            if match:
                version = match.group(1)
                patches = int(match.group(2)) if match.group(2) else 0
                results.append({"version": version, "patches": patches})
    
    if not results:
        versions = re.findall(r'\d+\.\d+\.\d+(?:-[a-zA-Z]+\.\d+)?', output)
        for v in set(versions):
            results.append({"version": v, "patches": 0})
    
    return results

def version_core(version):
    return version.split("-")[0]

def pick_latest_version(version_list):
    if not version_list:
        return None
    # Patch sayısı yüksek olan, sonra sürüm numarası büyük olan
    sorted_list = sorted(version_list, key=lambda x: (
        x["patches"],
        Version(version_core(x["version"]))
    ), reverse=True)
    return sorted_list[0]["version"]

def to_apk_mirror_version(version):
    return version.replace(".", "-")
