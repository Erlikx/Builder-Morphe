from core.apk.versions import extract_youtube_versions, pick_latest_version, to_apkmirror_version


def test_extract_versions_from_compatible_section():
    output = (
        "Some preamble text from the CLI\n"
        "Most common compatible versions:\n"
        "19.35.36 (5 patches)\n"
        "19.34.42 (3 patches)\n"
        "\n"
        "Trailing text that should not be reached\n"
    )
    result = extract_youtube_versions(output)
    assert result == [
        {"version": "19.35.36", "patches": 5},
        {"version": "19.34.42", "patches": 3},
    ]


def test_extract_versions_ignores_non_matching_lines_in_section():
    output = "Most common compatible versions:\nsome unrelated note\n19.35.36 (5 patches)\n\n"
    result = extract_youtube_versions(output)
    assert result == [{"version": "19.35.36", "patches": 5}]


def test_extract_versions_falls_back_when_no_section_header():
    output = "Available versions: 1.2.3, 1.2.4 and 2.0.0-beta.1 are supported"
    result = extract_youtube_versions(output)
    assert result == [
        {"version": "1.2.3", "patches": 0},
        {"version": "1.2.4", "patches": 0},
        {"version": "2.0.0-beta.1", "patches": 0},
    ]


def test_extract_versions_empty_input():
    assert extract_youtube_versions("") == []


def test_pick_latest_version_prefers_higher_patch_count():
    versions = [
        {"version": "1.2.2", "patches": 10},
        {"version": "1.2.4", "patches": 5},
    ]
    assert pick_latest_version(versions) == "1.2.2"


def test_pick_latest_version_breaks_ties_numerically_not_lexically():
    versions = [
        {"version": "1.2.3", "patches": 5},
        {"version": "1.2.10", "patches": 5},
    ]
    assert pick_latest_version(versions) == "1.2.10"


def test_pick_latest_version_empty_list():
    assert pick_latest_version([]) is None


def test_pick_latest_version_handles_unparseable_version_gracefully():
    versions = [{"version": "abc", "patches": 1}]
    assert pick_latest_version(versions) == "abc"


def test_to_apkmirror_version_replaces_dots_with_dashes():
    assert to_apkmirror_version("19.35.36") == "19-35-36"


def test_to_apkmirror_version_no_dots():
    assert to_apkmirror_version("19") == "19"
