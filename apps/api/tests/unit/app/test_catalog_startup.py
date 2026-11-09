"""Exercise env-only configuration at application and operator boundaries."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def environment(tmp_path: Path, mode: str) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("CATALOG_")
    }
    env.update(
        ANIBRIDGE_TEST_MODE="1",
        ANIBRIDGE_UPDATE_CHECK="0",
        DATA_DIR=str(tmp_path / "data"),
        DOWNLOAD_DIR=str(tmp_path / "downloads"),
        ANIWORLD_INSTALL_FOLDER=str(tmp_path / "upstream"),
        CATALOG_SITES="filmo.to" if mode == "query" else "aniworld.to",
        CATALOG_MODE=mode,
        CATALOG_API_URL="https://catalog.example" if mode == "query" else "",
        CATALOG_SOURCE_ID="fixture" if mode == "query" else "",
        CATALOG_API_TOKEN="synthetic-catalog-token-for-startup"
        if mode == "query"
        else "",
        CATALOG_API_TOKEN_FILE="",
        CATALOG_ALLOW_PRIVATE_HTTP="",
        DB_MIGRATE_ON_STARTUP="1",
        INDEXER_API_KEY="",
        QBIT_USERNAME="",
        QBIT_PASSWORD="",
        QBIT_SESSION_SECRET="",
        LOG_LEVEL="INFO",
    )
    return env


@pytest.mark.parametrize("mode", ["legacy", "query"])
def test_startup_selects_search_mode_and_warns_only_for_legacy(tmp_path, mode):
    program = """
import os
import httpx
from fastapi.testclient import TestClient
from app.main import app
from app.config import CATALOG_CONFIG
import app.catalog.runtime as runtime

mode = os.environ['CATALOG_MODE']
assert CATALOG_CONFIG.mode == mode
if mode == 'query':
    real_runtime = runtime.Runtime
    def unavailable(request):
        assert request.headers['authorization'] == 'Bearer ' + os.environ['CATALOG_API_TOKEN']
        return httpx.Response(503)
    # Preserve the real runtime/search/cache wiring without external traffic or
    # starting a downloader. No jobs are submitted by this startup regression.
    def isolated_runtime(*args, **kwargs):
        return real_runtime(*args, **kwargs, executor=object(), transport=httpx.MockTransport(unavailable))
    runtime.Runtime = isolated_runtime
with TestClient(app) as client:
    assert client.get('/health').status_code == 200
    if mode == 'query':
        assert app.state.catalog.config.token_file is None
        response = client.get('/torznab/api?t=search')
        assert response.status_code == 503
"""
    result = subprocess.run(
        [sys.executable, "-c", program],
        env=environment(tmp_path, mode),
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    output = result.stdout + result.stderr
    assert output.count("Legacy search is deprecated") == (1 if mode == "legacy" else 0)
    assert "synthetic-catalog-token-for-startup" not in output
    if mode == "legacy":
        assert "no longer actively developed or supported" in output
        assert "may be removed in a future release" in output


def test_correction_command_accepts_env_only_configuration(tmp_path):
    body = tmp_path / "correction.json"
    body.write_text('{"fixture":true}')
    program = """
import sys
from app.catalog import operator
from app.catalog.config import Config
async def capture(config, database, directory, body):
    assert isinstance(config, Config)
    assert config.mode == 'query' and config.token_file is None
    assert config.source_id == 'fixture'
    assert body == {'fixture': True}
    return {'id': 'fixture-correction'}
operator.apply = capture
operator.main()
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(body)],
        env=environment(tmp_path, "query"),
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    )
    assert "Created local correction fixture-correction" in result.stdout
    assert "synthetic-catalog-token-for-startup" not in result.stdout + result.stderr
