"""The serving command needs published catalogs and leases, never writer state."""

import asyncio
from dataclasses import replace

import httpx
import uvicorn
from test_query import NOW, TOKEN, seed

from catalog_worker import cli


def test_serve_and_populated_query_work_without_a_private_state_directory(
    tmp_path, monkeypatch
):
    state, config = seed(tmp_path)
    state.close()
    inaccessible = tmp_path / "not-a-directory"
    inaccessible.write_bytes(b"no private worker volume")
    config = replace(config, state_dir=inaccessible)
    token = tmp_path / "token"
    token.write_text(TOKEN)
    seen = {}
    monkeypatch.setattr(cli, "load", lambda _: config)
    monkeypatch.setattr(
        uvicorn, "run", lambda app, **kwargs: seen.update(app=app, **kwargs)
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "catalog-worker",
            "--config",
            "unused.json",
            "--serve",
            "--token-file",
            str(token),
        ],
    )
    cli.main()

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=seen["app"]),
            base_url="http://127.0.0.1",
            headers={"Authorization": "Bearer " + TOKEN},
        ) as client:
            response = await client.post(
                "/catalog/v1/query",
                json={
                    "provider": "aniworld.to",
                    "operation": "recent",
                    "params": {"t": "search"},
                    "limit": 100,
                },
            )
            assert response.status_code == 200 and response.json()["total"] == 2

    # The fixture's published rows must still be recent at the server's clock.
    monkeypatch.setattr("catalog_worker.query_server.time.time", lambda: NOW)
    asyncio.run(run())
    assert seen["access_log"] is False
    assert inaccessible.read_bytes() == b"no private worker volume"
