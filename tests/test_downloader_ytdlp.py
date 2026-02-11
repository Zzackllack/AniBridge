from pathlib import Path


def test_ydl_download_applies_rate_limit(monkeypatch, tmp_path: Path):
    import importlib

    mod = importlib.import_module("app.core.downloader.ytdlp")
    monkeypatch.setattr(mod, "DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC", 5242880)
    monkeypatch.setattr(mod, "yt_dlp_proxy", lambda: None)

    captured: dict[str, object] = {}

    class DummyYDL:
        def __init__(self, opts):
            captured["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, _url, download=True):
            return {"title": "demo", "ext": "mp4"}

        def prepare_filename(self, _info):
            return str(tmp_path / "demo.mp4")

    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", DummyYDL)

    path, _info = mod._ydl_download("https://example.test/video", tmp_path)

    assert path == tmp_path / "demo.mp4"
    assert captured["opts"]["ratelimit"] == 5242880


def test_ydl_download_omits_rate_limit_when_disabled(monkeypatch, tmp_path: Path):
    import importlib

    mod = importlib.import_module("app.core.downloader.ytdlp")
    monkeypatch.setattr(mod, "DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC", 0)
    monkeypatch.setattr(mod, "yt_dlp_proxy", lambda: None)

    captured: dict[str, object] = {}

    class DummyYDL:
        def __init__(self, opts):
            captured["opts"] = opts

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, _url, download=True):
            return {"title": "demo", "ext": "mp4"}

        def prepare_filename(self, _info):
            return str(tmp_path / "demo.mp4")

    monkeypatch.setattr(mod.yt_dlp, "YoutubeDL", DummyYDL)

    path, _info = mod._ydl_download("https://example.test/video", tmp_path)

    assert path == tmp_path / "demo.mp4"
    assert "ratelimit" not in captured["opts"]
