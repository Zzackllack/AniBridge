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


def test_provider_order_normalizes_case_and_drops_invalid(monkeypatch):
    monkeypatch.setenv("PROVIDER_ORDER", " voe , filemoon,invalid,gxplayer ")
    import importlib
    import sys
    import app

    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    if hasattr(app, "config"):
        delattr(app, "config")
    cfg = importlib.import_module("app.config")

    assert cfg.VIDEO_HOST_ORDER == ["VOE", "Filemoon", "GXPlayer"]
    assert cfg.PROVIDER_ORDER == ["VOE", "Filemoon", "GXPlayer"]


def test_repo_root_defaults_anchor_local_data_paths() -> None:
    import app.config as cfg

    assert (cfg.REPO_ROOT / ".github").exists()
    assert (cfg.REPO_ROOT / "apps" / "api" / "pyproject.toml").exists()
    assert cfg.DATA_DIR == (cfg.REPO_ROOT / "data").resolve()
    assert cfg.DOWNLOAD_DIR == (cfg.REPO_ROOT / "data" / "downloads").resolve()


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


def test_provider_redirect_settings(monkeypatch):
    """
    Verify that provider redirect configuration environment variables are parsed into integer constants and that an invalid download rate limit falls back to zero.

    Asserts that PROVIDER_REDIRECT_TIMEOUT_SECONDS, PROVIDER_REDIRECT_RETRIES, and PROVIDER_CHALLENGE_BACKOFF_SECONDS are read from the environment and converted to 15, 4, and 120 respectively, and that DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC set to a non-numeric value results in 0.
    """
    import importlib
    import app
    import sys

    monkeypatch.setenv("PROVIDER_REDIRECT_TIMEOUT_SECONDS", "15")
    monkeypatch.setenv("PROVIDER_REDIRECT_RETRIES", "4")
    monkeypatch.setenv("PROVIDER_CHALLENGE_BACKOFF_SECONDS", "120")

    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    if hasattr(app, "config"):
        delattr(app, "config")
    cfg = importlib.import_module("app.config")
    cfg = importlib.reload(cfg)

    assert cfg.PROVIDER_REDIRECT_TIMEOUT_SECONDS == 15
    assert cfg.PROVIDER_REDIRECT_RETRIES == 4
    assert cfg.PROVIDER_CHALLENGE_BACKOFF_SECONDS == 120

    monkeypatch.setenv("DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC", "not-a-number")
    if "app.config" in sys.modules:
        del sys.modules["app.config"]
    if hasattr(app, "config"):
        delattr(app, "config")
    cfg = importlib.import_module("app.config")
    cfg = importlib.reload(cfg)
    assert cfg.DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC == 0
