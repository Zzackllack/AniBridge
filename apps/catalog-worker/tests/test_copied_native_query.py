"""A copied-ledger oracle must not expire targeted catalog releases."""

import asyncio
import importlib.util
from pathlib import Path

import httpx
from catalog_core.protocol import Request
from test_query import NOW, TOKEN, seed

from catalog_worker.query_server import create_app
from catalog_worker.read_catalog import publish


def test_targeted_sql_oracle_and_full_response_include_old_releases(tmp_path):
    path = (
        Path(__file__).resolve().parents[3]
        / "scripts/catalog/query_pilot/verify_copied_catalog.py"
    )
    spec = importlib.util.spec_from_file_location("copied_catalog_verifier", path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    state, config = seed(tmp_path)
    try:
        with state.db:
            state.db.execute("UPDATE release SET first_seen_at=?", (NOW - 60 * 86400,))
        publish(config, state, NOW + 1)
        tid = state.db.execute("SELECT title_id FROM title").fetchone()[0]
        expected = helper.native_total(state.db, tid, 0, 1)
        assert expected == 2
        app = create_app(config.output_dir, TOKEN, now=NOW + 1)

        async def run():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://127.0.0.1",
                headers={"Authorization": "Bearer " + TOKEN},
            ) as http:
                request = Request(
                    provider="aniworld.to",
                    operation="native",
                    params={"t": "search"},
                    title_ids=[tid],
                    season=0,
                    episode=1,
                )
                response = await http.post(
                    "/catalog/v1/query", json=request.model_dump()
                )
                assert response.status_code == 200
                body = response.json()
                assert body["total"] == expected and len(body["rows"]) == expected
                recent = Request(
                    provider="aniworld.to",
                    operation="recent",
                    params={"t": "search"},
                    limit=100,
                )
                response = await http.post(
                    "/catalog/v1/query", json=recent.model_dump()
                )
                assert response.status_code == 200 and response.json()["total"] == 0

        asyncio.run(run())
    finally:
        state.close()
