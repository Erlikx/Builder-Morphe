import pytest

from core import validate


def test_real_config_passes_validation():
    validate.validate_config()


def test_app_missing_from_process_order_is_caught(monkeypatch):
    monkeypatch.setitem(
        validate.APPS_CONFIG,
        "ghost-app",
        {
            "pkg": "com.example.ghost",
            "name": "ghost",
            "patch_source": "morphe",
            "arch": "arm64-v8a",
            "icon": "https://example.com/icon.png",
        },
    )
    with pytest.raises(validate.ConfigError, match="ghost-app"):
        validate.validate_config()


def test_process_order_referencing_unknown_app_is_caught(monkeypatch):
    monkeypatch.setattr(validate, "PROCESS_ORDER", [*validate.PROCESS_ORDER, "does-not-exist"])
    with pytest.raises(validate.ConfigError, match="does-not-exist"):
        validate.validate_config()


def test_unknown_patch_source_is_caught(monkeypatch):
    original = dict(validate.APPS_CONFIG["youtube"])
    monkeypatch.setitem(validate.APPS_CONFIG, "youtube", {**original, "patch_source": "totally-made-up-source"})
    with pytest.raises(validate.ConfigError, match="totally-made-up-source"):
        validate.validate_config()


def test_exclude_as_string_instead_of_list_is_caught(monkeypatch):
    original = dict(validate.APPS_CONFIG["twitter"])
    monkeypatch.setitem(validate.APPS_CONFIG, "twitter", {**original, "exclude": "Dynamic color"})
    with pytest.raises(validate.ConfigError, match="should be a list"):
        validate.validate_config()


def test_apkmirror_app_missing_from_app_sites_is_caught(monkeypatch):
    from core.sources import apkmirror

    original = dict(apkmirror.APP_SITES)
    del original["youtube"]
    monkeypatch.setattr(apkmirror, "APP_SITES", original)
    with pytest.raises(validate.ConfigError, match="APP_SITES"):
        validate.validate_config()
