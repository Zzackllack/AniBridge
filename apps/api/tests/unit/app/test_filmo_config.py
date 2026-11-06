"""Provider opt-in must fail clearly before legacy searches can be accepted."""

import json
import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize("mode", ["legacy", "query"])
def test_filmo_requires_explicit_query_configuration(tmp_path, mode):
    token = tmp_path / "token"
    token.write_text("synthetic-test-token")
    config = tmp_path / "client.json"
    config.write_text(
        json.dumps(
            {
                "mode": "query",
                "origin": "https://metadata.example",
                "source_id": "fixture",
                "token_file": str(token),
            }
        )
    )
    environment = {
        **os.environ,
        "CATALOG_SITES": "filmo.to",
        "LOG_LEVEL": "ERROR",
        "DATA_DIR": str(tmp_path / "data"),
        "DOWNLOAD_DIR": str(tmp_path / "downloads"),
        "ANIWORLD_INSTALL_FOLDER": str(tmp_path / "upstream"),
        "CATALOG_CONFIG_FILE": str(config) if mode == "query" else "",
    }
    program = """
import os
try:
    import app.config as config
except ValueError as error:
    assert os.environ['CATALOG_CONFIG_FILE'] == ''
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
