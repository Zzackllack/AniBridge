"""Provider opt-in must fail clearly before legacy searches can be accepted."""

import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("mode", ["legacy", "query"])
def test_filmo_requires_explicit_query_configuration(tmp_path, mode):
    environment = {
        **os.environ,
        "CATALOG_SITES": "filmo.to",
        "LOG_LEVEL": "ERROR",
        "DATA_DIR": str(tmp_path / "data"),
        "DOWNLOAD_DIR": str(tmp_path / "downloads"),
        "ANIWORLD_INSTALL_FOLDER": str(tmp_path / "upstream"),
        "CATALOG_MODE": mode,
        "CATALOG_API_URL": "https://metadata.example" if mode == "query" else "",
        "CATALOG_SOURCE_ID": "fixture" if mode == "query" else "",
        "CATALOG_API_TOKEN": (
            "synthetic-catalog-token-for-filmo" if mode == "query" else ""
        ),
        "CATALOG_API_TOKEN_FILE": "",
        "CATALOG_ALLOW_PRIVATE_HTTP": "",
    }
    program = """
import os
try:
    import app.config as config
except ValueError as error:
    assert os.environ['CATALOG_MODE'] == 'legacy'
    assert str(error).startswith('Filmo requires catalog query mode')
else:
    assert config.CATALOG_CONFIG.mode == 'query'
    assert set(config.CATALOG_SITE_CONFIGS) == {'filmo.to'}
"""
    subprocess.run(
        [sys.executable, "-c", program],
        env=environment,
        check=True,
        capture_output=True,
        timeout=10,
    )
