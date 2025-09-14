import importlib
from pathlib import Path


def test_get_version_uses_package_metadata(monkeypatch):
    # Force VERSION file to be treated as missing
    orig_exists = Path.exists

    def fake_exists(self):  # type: ignore[no-redef]
        return False if self.name == "VERSION" else orig_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists, raising=False)

    # Patch importlib.metadata.version to return a known value
    import importlib.metadata as im

    monkeypatch.setattr(im, "version", lambda name: "9.9.9")

    from app import _version as ver

    assert ver.get_version() == "9.9.9"


def test_get_version_fallback_to_default(monkeypatch):
    # Force VERSION file to be treated as missing
    orig_exists = Path.exists

    def fake_exists(self):  # type: ignore[no-redef]
        return False if self.name == "VERSION" else orig_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists, raising=False)

    # Patch importlib.metadata.version to raise, triggering default fallback
    import importlib.metadata as im

    def raise_err(_):
        raise RuntimeError("no package metadata")

    monkeypatch.setattr(im, "version", raise_err)

    from app import _version as ver

    assert ver.get_version() == "0.0.0"

