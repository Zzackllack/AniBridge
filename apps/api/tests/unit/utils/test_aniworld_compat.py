from __future__ import annotations

import os

import pytest

from app.utils import aniworld_compat


@pytest.fixture(autouse=True)
def clear_aniworld_path_cache():
    aniworld_compat.prepare_aniworld_home.cache_clear()
    yield
    aniworld_compat.prepare_aniworld_home.cache_clear()


def test_prepare_aniworld_home_defaults_under_data_dir(monkeypatch, tmp_path):
    original_home = os.environ.get("HOME")
    monkeypatch.delenv("ANIWORLD_INSTALL_FOLDER", raising=False)
    monkeypatch.setattr(aniworld_compat, "DATA_DIR", tmp_path / "data")
    install_dir = aniworld_compat.prepare_aniworld_home()

    assert install_dir == (tmp_path / "data" / "aniworld").resolve()
    assert os.environ["ANIWORLD_INSTALL_FOLDER"] == str(install_dir)
    assert os.environ.get("HOME") == original_home


def test_prepare_aniworld_home_preserves_explicit_directory(monkeypatch, tmp_path):
    configured = tmp_path / "upstream-config"
    monkeypatch.setenv("ANIWORLD_INSTALL_FOLDER", str(configured))
    assert aniworld_compat.prepare_aniworld_home() == configured.resolve()


def test_prepare_aniworld_home_reports_unwritable_target(monkeypatch, tmp_path):
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_text("occupied", encoding="utf-8")
    monkeypatch.setenv(
        "ANIWORLD_INSTALL_FOLDER",
        str(blocking_file / "upstream-config"),
    )
    with pytest.raises(RuntimeError, match="not writable"):
        aniworld_compat.prepare_aniworld_home()
