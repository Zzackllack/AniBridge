"""Metadata API to local corrections/RSS and frozen durable acceptance."""

import asyncio
import json
import sqlite3
import sys
import time
from pathlib import Path
from uuid import uuid4

from contextlib import closing
import httpx
from catalog_core import fixtures, magnet, schema
from catalog_core.query_client import Cache, Client

from app.catalog.jobs import Jobs
from app.catalog.overrides import fingerprint
from app.catalog.query_local import Search
from app.catalog.search import rss
from app.catalog.state_schema import STATEMENTS

# Load the separate collector's read factory, without API startup imports.
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "catalog-worker" / "src"))
from catalog_worker.query_server import create_app

TOKEN = "disposable-query-fixture-token"
NOW = int(time.time())


def setup(tmp_path):
    root = tmp_path / "read"
    _, metadata, _, _ = fixtures.build(root, now=NOW)
    metadata["database"] = "fixture.sqlite"
    (root / "current.json").write_text(json.dumps(metadata))
    database = tmp_path / "private.sqlite"
    with closing(sqlite3.connect(database)) as db, db:
        db.execute(
            "CREATE TABLE job(id TEXT PRIMARY KEY,status TEXT,progress REAL,downloaded_bytes INTEGER,total_bytes INTEGER,speed REAL,eta INTEGER,message TEXT,result_path TEXT,source_site TEXT,created_at TEXT,updated_at TEXT)"
        )
        db.execute(
            "CREATE TABLE clienttask(hash TEXT PRIMARY KEY,name TEXT,slug TEXT,season INTEGER,episode INTEGER,language TEXT,site TEXT,job_id TEXT,save_path TEXT,category TEXT,added_on TEXT,completion_on TEXT,state TEXT)"
        )
        for statement in STATEMENTS:
            db.execute(statement)
    app = create_app(root, TOKEN, now=NOW)
    client = Client(
        "http://127.0.0.1",
        "synthetic",
        TOKEN,
        Cache(tmp_path / "cache"),
        transport=httpx.ASGITransport(app=app),
    )
    return client, Search(client, database, tmp_path), database, root


def insert_override(database, root, entity_kind, target):
    with closing(schema.connect(root / "fixture.sqlite")) as catalog:
        row = catalog.execute("SELECT * FROM entity").fetchone()
        body = {
            "provider": "aniworld.to",
            "entity_kind": entity_kind,
            "title_id": row["title_id"],
            "entity_id": row["entity_id"] if entity_kind == "episode" else None,
            "target": {
                "namespace": "tvdb",
                "external_id": target[0],
                "season": target[1],
                "episode": target[2],
            },
            "reason": "Reviewed fixture correspondence",
            "enabled": True,
        }
        body["fingerprint"] = fingerprint(catalog, body)
    with closing(sqlite3.connect(database)) as db, db:
        db.execute(
            "INSERT INTO catalog_override VALUES(?,?,?,?,?,?,1,?,?)",
            (
                str(uuid4()),
                "aniworld.to",
                body["title_id"],
                body["entity_id"],
                "tvdb",
                json.dumps(body),
                NOW,
                NOW,
            ),
        )


def test_local_correction_discovers_new_id_before_season_filter(tmp_path):
    client, search, database, root = setup(tmp_path)
    insert_override(database, root, "title", ("999", None, None))
    insert_override(database, root, "episode", ("999", 3, 9))

    async def run():
        rows, total, _ = await search.search(
            {
                "t": "tvsearch",
                "tvdbid": "999",
                "season": "3",
                "ep": "9",
                "limit": "1",
                "offset": "1",
            },
            now=NOW,
        )
        assert total == 4 and len(rows) == 1
        assert (rows[0]["season"], rows[0]["episode"]) == (3, 9)
        assert (rows[0]["native_season"], rows[0]["native_episode"]) == (1, 2)
        assert client.requests == 2
        with closing(sqlite3.connect(database)) as db, db:
            db.execute("DELETE FROM catalog_override")
        original, total, _ = await search.search(
            {"t": "tvsearch", "tvdbid": "123", "season": "0", "ep": "1"}, now=NOW
        )
        assert total == 4 and any(
            r["release_id"] == rows[0]["release_id"] for r in original
        )
        await client.close()

    asyncio.run(run())


def test_rss_language_and_frozen_grab_after_outage(tmp_path):
    client, search, database, _ = setup(tmp_path)

    async def run():
        rows, total, _ = await search.search(
            {"t": "tvsearch", "tvdbid": "123", "season": "0"},
            now=NOW,
            languages={"aniworld.to": {"de-dub", "en-sub"}},
        )
        assert total == 2 and {r["language"] for r in rows} == {"de-dub", "en-sub"}
        feed = rss(rows, total, 0)
        assert b"720p" not in feed and b"H264" not in feed
        payload = {key: rows[0][key] for key in magnet.PAYLOAD_FIELDS - {"canonical"}}
        payload["canonical"] = {
            key: rows[0][key]
            for key in ("namespace", "external_id", "season", "episode")
        }
        downloads = tmp_path / "downloads"
        downloads.mkdir()
        jobs = Jobs(database, downloads, {"aniworld.to"})
        job = jobs.admit(magnet.encode(payload, "Example"), NOW, paused=True)[0]
        frozen = jobs.get(job)["payload"]
        await client.close()
        jobs = Jobs(database, downloads, {"aniworld.to"})
        jobs.recover(NOW + 60, startup=True)
        assert jobs.get(job)["status"] == "paused"
        jobs.action(job, "resume", NOW + 61)
        claim = jobs.claim(NOW + 61)
        jobs.finish(job, claim["generation"], "challenge", NOW + 62)
        assert jobs.get(job)["status"] == "blocked"
        jobs.action(job, "retry", NOW + 123)
        assert jobs.get(job)["payload"] == frozen
        assert jobs.get(job)["status"] == "queued"

    asyncio.run(run())


def test_recent_mode_variant_pagination(tmp_path):
    client, search, _, _ = setup(tmp_path)

    async def run():
        rows, total, _ = await search.search(
            {"t": "search", "limit": "3", "offset": "1"},
            now=NOW,
            modes=("download", "strm"),
            languages={"aniworld.to": {"de-dub", "en-sub"}},
        )
        assert total == 4 and len(rows) == 3
        assert rows[0]["mode"] == "strm"
        await client.close()

    asyncio.run(run())


def test_production_torznab_route_and_explicit_outage(tmp_path):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from app.catalog.http import router

    client, search, _, _ = setup(tmp_path)
    app = FastAPI()
    app.state.catalog = SimpleNamespace(search=search)
    app.include_router(router)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://local"
        ) as http:
            params = {"t": "tvsearch", "tvdbid": "123", "season": "0"}
            result = await http.get("/torznab/api", params=params)
            assert result.status_code == 200
            assert b"<item>" in result.content
            await client.http.aclose()

            async def unavailable(request):
                return httpx.Response(503)

            client.http = httpx.AsyncClient(transport=httpx.MockTransport(unavailable))
            client.ttl_s = 0
            stale = await http.get("/torznab/api", params=params)
            assert (
                stale.status_code == 200
                and stale.headers["X-AniBridge-Catalog-Stale"] == "true"
            )
            missing = await http.get(
                "/torznab/api", params={"t": "tvsearch", "tvdbid": "99999"}
            )
            assert missing.status_code == 503 and b'code="900"' in missing.content
            assert (
                await http.get("/torznab/api", params={"t": "caps"})
            ).status_code == 200
        await client.close()

    asyncio.run(run())


def test_tmdb_request_uses_tmdb_episode_coordinates(tmp_path):
    from catalog_core import identity, artifact

    client, search, _, root = setup(tmp_path)
    with closing(sqlite3.connect(root / "fixture.sqlite")) as db, db:
        tid = db.execute("SELECT title_id FROM title").fetchone()[0]
        eid = db.execute("SELECT entity_id FROM entity").fetchone()[0]
        mid = identity.mapping_id("aniworld.to", tid, "tmdb-tv", "456")
        db.execute(
            "INSERT INTO canonical_title VALUES(?,?,?,?,?,?,?)",
            (mid, tid, "tmdb-tv", "456", "synthetic-v1", "reviewed", NOW),
        )
        db.execute(
            "INSERT INTO canonical_episode VALUES(?,?,?,?,?,?,?)",
            (mid, eid, 3, 9, None, "reviewed", NOW),
        )
    metadata = json.loads((root / "current.json").read_text())
    metadata["artifact"]["sqlite_sha256"] = artifact.sha256(root / "fixture.sqlite")
    (root / "current.json").write_text(json.dumps(metadata))

    async def run():
        rows, total, _ = await search.search(
            {"t": "tvsearch", "tmdbid": "456", "season": "3", "ep": "9"}, now=NOW
        )
        assert total == 4 and all(
            (r["namespace"], r["season"], r["episode"]) == ("tmdb-tv", 3, 9)
            for r in rows
        )
        assert all((r["native_season"], r["native_episode"]) == (1, 2) for r in rows)
        await client.close()

    asyncio.run(run())
