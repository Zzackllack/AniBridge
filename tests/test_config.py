def test_provider_order_parsing(monkeypatch):
    monkeypatch.setenv("PROVIDER_ORDER", "  VOE , , Filemoon ,, Streamtape  ")
    # reload module to pick env
    import sys

    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    from app import config as cfg

    assert cfg.PROVIDER_ORDER == ["VOE", "Filemoon", "Streamtape"]


def test_max_concurrency_floor(monkeypatch):
    monkeypatch.setenv("MAX_CONCURRENCY", "0")
    import importlib
    from app import config as cfg

    # Force re-evaluation of module-level constants
    cfg = importlib.reload(cfg)

    assert cfg.MAX_CONCURRENCY == 1


def _reload_config(monkeypatch, env_overrides: dict[str, str] | None = None):
    keys_to_clear = [
        "CATALOG_SITES",
        "SITE_BASE_URL_ANIWORLD",
        "SITE_BASE_URL_STO",
        "PREFERRED_LANGUAGES_ANIWORLD",
        "PREFERRED_LANGUAGES_STO",
        "CATALOG_SEARCH_TIMEOUT_SECONDS",
        "SITE_SEARCH_TIMEOUT_SECONDS_ANIWORLD",
        "SITE_SEARCH_TIMEOUT_SECONDS_STO",
    ]
    for key in keys_to_clear:
        monkeypatch.delenv(key, raising=False)
    if env_overrides:
        for key, value in env_overrides.items():
            monkeypatch.setenv(key, value)

    import sys
    import importlib

    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    return importlib.import_module("app.config")


def test_catalog_config_defaults(monkeypatch):
    cfg = _reload_config(monkeypatch)
    assert cfg.CATALOG_SITE_IDS == ["aniworld", "sto"]
    assert cfg.ENABLED_CATALOG_IDS == ("aniworld", "sto")

    aniworld = cfg.CATALOG_CONFIG_BY_ID["aniworld"]
    sto = cfg.CATALOG_CONFIG_BY_ID["sto"]

    assert aniworld["base_url"] == "https://aniworld.to"
    assert sto["base_url"] == "http://186.2.175.5"
    assert aniworld["search_priority"] == 1
    assert sto["search_priority"] == 2
    assert aniworld["preferred_languages"][0] == "German Dub"
    assert sto["preferred_languages"][0] == "English Dub"


def test_catalog_config_env_overrides(monkeypatch):
    cfg = _reload_config(
        monkeypatch,
        {
            "CATALOG_SITES": "sto,aniworld",
            "SITE_BASE_URL_STO": "https://streaming.example",
            "PREFERRED_LANGUAGES_STO": "English Sub,English Dub",
            "CATALOG_SEARCH_TIMEOUT_SECONDS": "15",
            "SITE_SEARCH_TIMEOUT_SECONDS_ANIWORLD": "20",
        },
    )
    assert cfg.CATALOG_SITE_IDS == ["sto", "aniworld"]
    assert cfg.ENABLED_CATALOG_IDS == ("sto", "aniworld")

    sto = cfg.CATALOG_CONFIG_BY_ID["sto"]
    aniworld = cfg.CATALOG_CONFIG_BY_ID["aniworld"]

    assert sto["base_url"] == "https://streaming.example"
    assert sto["preferred_languages"] == ["English Sub", "English Dub"]
    assert sto["search_priority"] == 1
    assert sto["search_timeout_seconds"] == 15
    assert aniworld["search_timeout_seconds"] == 20


def test_catalog_config_invalid_entries(monkeypatch):
    cfg = _reload_config(
        monkeypatch,
        {
            "CATALOG_SITES": "invalidsite",
        },
    )
    assert cfg.CATALOG_SITE_IDS == ["aniworld"]
    assert cfg.ENABLED_CATALOG_IDS == ("aniworld",)
