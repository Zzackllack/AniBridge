def test_provider_order_parsing(monkeypatch):
    monkeypatch.setenv("PROVIDER_ORDER", "  VOE , , Filemoon ,, Streamtape  ")
    # reload module to pick env
    import importlib
    import sys
    import app

    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    if hasattr(app, "config"):
        delattr(app, "config")
    cfg = importlib.import_module("app.config")

    assert cfg.PROVIDER_ORDER == ["VOE", "Filemoon", "Streamtape"]


def test_max_concurrency_floor(monkeypatch):
    monkeypatch.setenv("MAX_CONCURRENCY", "0")
    import importlib
    import app
    import sys

    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    if hasattr(app, "config"):
        delattr(app, "config")
    cfg = importlib.import_module("app.config")

    # Force re-evaluation of module-level constants
    cfg = importlib.reload(cfg)

    assert cfg.MAX_CONCURRENCY == 1


def test_download_rate_limit_parsing(monkeypatch):
    monkeypatch.setenv("DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC", "5242880")
    import importlib
    import app
    import sys

    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    if hasattr(app, "config"):
        delattr(app, "config")
    cfg = importlib.import_module("app.config")
    cfg = importlib.reload(cfg)

    assert cfg.DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC == 5242880


def test_download_rate_limit_invalid_or_negative_defaults_to_zero(monkeypatch):
    import importlib
    import app
    import sys

    monkeypatch.setenv("DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC", "-1")
    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    if hasattr(app, "config"):
        delattr(app, "config")
    cfg = importlib.import_module("app.config")
    cfg = importlib.reload(cfg)
    assert cfg.DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC == 0

    monkeypatch.setenv("DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC", "not-a-number")
    cfg = importlib.reload(cfg)
    assert cfg.DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC == 0
