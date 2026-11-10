"""Focused production read contract, replacement and outage tests."""

import asyncio
from pathlib import Path

import httpx
import pytest
from catalog_core import identity
from catalog_core.protocol import Request
from catalog_core.query_client import Cache, Client, Unavailable

from catalog_worker.aniworld import Link, Page
from catalog_worker.config import LIMITS, Config
from catalog_worker.query_server import create_app
from catalog_worker.read_catalog import publish
from catalog_worker.state import State

NOW = 1800000000
TOKEN = "disposable-fixture-token"


def seed(tmp_path: Path):
    state = State(tmp_path / "state" / "aniworld.to.sqlite", "aniworld.to")
    title = "/anime/stream/example"
    path = title + "/staffel-1/episode-2"
    state.listing(Page((Link(title, "Example"),), (), 0, None), NOW)
    state.detail(state.claim(NOW), Page((Link(path, "Second"),), (), 0, "Example"), NOW)
    state.detail(state.claim(NOW), Page((), ("de-dub", "en-sub"), 0, "Second"), NOW)
    state.db.execute(
        "INSERT INTO canonical_title VALUES(?,?,?,?,?,?,?)",
        (
            identity.mapping_id(
                "aniworld.to", identity.title_id("aniworld.to", title), "tvdb", "123"
            ),
            identity.title_id("aniworld.to", title),
            "tvdb",
            "123",
            "synthetic-v1",
            "reviewed",
            NOW,
        ),
    )
    state.db.execute(
        "INSERT INTO canonical_episode VALUES(?,?,?,?,?,?,?)",
        (
            identity.mapping_id(
                "aniworld.to", identity.title_id("aniworld.to", title), "tvdb", "123"
            ),
            identity.entity_id("aniworld.to", path),
            0,
            1,
            None,
            "reviewed",
            NOW,
        ),
    )
    state.db.commit()
    config = Config(
        {"aniworld.to": "https://aniworld.to"},
        {"tv": "off"},
        tmp_path / "state",
        tmp_path / "read",
        tmp_path / "unused",
        "synthetic",
        "127.0.0.1",
        8080,
        {key: value[0] for key, value in LIMITS.items()},
        frozenset({"synthetic-v1"}),
    )
    publish(config, state, NOW)
    return state, config


def test_native_identity_and_outage_coalescing(tmp_path):
    state, config = seed(tmp_path)
    app = create_app(config.output_dir, TOKEN, now=NOW)

    async def run():
        client = Client(
            "http://127.0.0.1",
            "synthetic",
            TOKEN,
            Cache(tmp_path / "cache"),
            transport=httpx.ASGITransport(app=app),
        )
        req = Request(operation="titles", params={"t": "tvsearch", "tvdbid": "123"})
        batch = await client.fetch(req, now=NOW)
        assert len(batch.response.titles) == 1
        native = Request(
            operation="native",
            params={"t": "search"},
            title_ids=[batch.response.titles[0].title_id],
        )
        results = await asyncio.gather(
            *(client.fetch(native, now=NOW) for _ in range(8))
        )
        assert client.requests == 2
        assert len(results[0].response.rows) == 2
        row = results[0].response.rows[0]
        assert (row.native_season, row.native_episode, row.season, row.episode) == (
            1,
            2,
            0,
            1,
        )
        assert row.first_seen_at == NOW
        await client.close()

        async def unavailable(request):
            return httpx.Response(503)

        offline = Client(
            "http://127.0.0.1",
            "synthetic",
            TOKEN,
            Cache(tmp_path / "cache"),
            transport=httpx.MockTransport(unavailable),
        )
        stale = await offline.fetch(native, now=NOW + 61)
        assert stale.state == "stale" and stale.age_s == 61
        with pytest.raises(Unavailable):
            await offline.fetch(
                Request(operation="titles", params={"t": "search", "q": "missing"}),
                now=NOW + 61,
            )
        await offline.close()

    try:
        asyncio.run(run())
    finally:
        state.close()


def test_replacement_and_authenticated_admission(tmp_path):
    state, config = seed(tmp_path)
    app = create_app(config.output_dir, TOKEN, now=NOW)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1"
        ) as http:
            req = Request(operation="recent", params={"t": "search"}, limit=100)
            assert (
                await http.post("/catalog/v1/query", json=req.model_dump())
            ).status_code == 401
            headers = {"Authorization": "Bearer " + TOKEN}
            first = await http.post(
                "/catalog/v1/query", json=req.model_dump(), headers=headers
            )
            assert first.status_code == 200, first.text
            publish(config, state, NOW + 1)
            second = await http.post(
                "/catalog/v1/query", json=req.model_dump(), headers=headers
            )
            assert second.json()["revision"] == first.json()["revision"] + 1
            assert [r["release_id"] for r in second.json()["rows"]] == [
                r["release_id"] for r in first.json()["rows"]
            ]
            assert (
                await http.post(
                    "/catalog/v1/query", content=b"x" * 16385, headers=headers
                )
            ).status_code == 413
            app.state.admission.active = 8
            assert (
                await http.post(
                    "/catalog/v1/query", json=req.model_dump(), headers=headers
                )
            ).status_code == 429

    try:
        asyncio.run(run())
    finally:
        state.close()


@pytest.mark.parametrize(
    "fault",
    ["source", "digest", "language", "regression", "oversize", "duplicate", "auth"],
)
def test_invalid_responses_never_use_stale_cache(tmp_path, fault):
    state, config = seed(tmp_path)
    app = create_app(config.output_dir, TOKEN, now=NOW)
    req = Request(operation="recent", params={"t": "search"}, limit=100)

    async def run():
        cache = Cache(tmp_path / "cache")
        client = Client(
            "http://127.0.0.1",
            "synthetic",
            TOKEN,
            cache,
            transport=httpx.ASGITransport(app=app),
        )
        good = (await client.fetch(req, now=NOW)).response.model_dump()
        await client.close()
        if fault == "source":
            good["source_id"] = "other"
        if fault == "digest":
            good["query_digest"] = "0" * 64
        if fault == "language":
            good["rows"][0]["language"] = "invented"
        if fault == "regression":
            good["revision"] = 0

        async def corrupt(request):
            if fault == "oversize":
                return httpx.Response(
                    200,
                    content=b"x" * (2 * 1024**2 + 1),
                    headers={"content-type": "application/json"},
                )
            if fault == "duplicate":
                return httpx.Response(
                    200,
                    content=b'{"version":1,"version":1}',
                    headers={"content-type": "application/json"},
                )
            if fault == "auth":
                return httpx.Response(401)
            return httpx.Response(200, json=good)

        bad = Client(
            "http://127.0.0.1",
            "synthetic",
            TOKEN,
            cache,
            transport=httpx.MockTransport(corrupt),
        )
        with pytest.raises(Unavailable):
            await bad.fetch(req, now=NOW + 61)
        await bad.close()

    try:
        asyncio.run(run())
    finally:
        state.close()


def test_cache_eviction_corruption_negative_source_change_and_waiter_cancel(tmp_path):
    state, config = seed(tmp_path)
    app = create_app(config.output_dir, TOKEN, now=NOW)
    req = Request(operation="recent", params={"t": "search"}, limit=100)

    async def run():
        cache = Cache(tmp_path / "cache", entries=2, payload_bytes=65536)
        client = Client(
            "http://127.0.0.1",
            "synthetic",
            TOKEN,
            cache,
            transport=httpx.ASGITransport(app=app),
        )
        first = await client.fetch(req, now=NOW)
        assert (await client.fetch(req, now=NOW + 1)).state == "hit"
        empty = Request(operation="titles", params={"t": "search", "q": "absent"})
        await client.fetch(empty, now=NOW)
        await client.close()

        async def outage(request):
            return httpx.Response(503)

        offline = Client(
            "http://127.0.0.1",
            "synthetic",
            TOKEN,
            cache,
            transport=httpx.MockTransport(outage),
        )
        with pytest.raises(Unavailable):
            await offline.fetch(empty, now=NOW + 61)
        with cache.connect() as db:
            db.execute(
                "UPDATE entry SET body=? WHERE key=?", (b"{bad", offline.key(req))
            )
        with pytest.raises(Unavailable):
            await offline.fetch(req, now=NOW + 61)
        await offline.close()
        switched = Client(
            "http://localhost",
            "synthetic",
            TOKEN,
            cache,
            transport=httpx.MockTransport(outage),
        )
        with pytest.raises(Unavailable):
            await switched.fetch(req, now=NOW + 1)
        await switched.close()
        cache.clear()
        started = asyncio.Event()

        async def slow(request):
            started.set()
            await asyncio.sleep(0.05)
            return httpx.Response(200, json=first.response.model_dump())

        shared = Client(
            "http://127.0.0.1",
            "synthetic",
            TOKEN,
            cache,
            transport=httpx.MockTransport(slow),
        )
        a = asyncio.create_task(shared.fetch(req, now=NOW))
        b = asyncio.create_task(shared.fetch(req, now=NOW))
        await started.wait()
        a.cancel()
        await asyncio.gather(a, return_exceptions=True)
        assert (await b).state == "miss" and shared.requests == 1
        await shared.close()
        for key in ("a", "b", "c"):
            cache.put(key, b"{}", NOW)
        with cache.connect() as db:
            assert db.execute("SELECT count(*) FROM entry").fetchone()[0] == 2
        assert cache.filename.stat().st_size <= 16 * 1024**2

    try:
        asyncio.run(run())
    finally:
        state.close()


def test_concurrent_reads_and_atomic_replacement(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    from catalog_worker.query_reader import execute

    state, config = seed(tmp_path)
    req = Request(operation="recent", params={"t": "search"}, limit=100)
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = [
                pool.submit(execute, config.output_dir, req, NOW) for _ in range(32)
            ]
            publish(config, state, NOW + 1)
            responses = [f.result() for f in futures]
        assert {r.revision for r in responses} <= {1, 2}
        assert all(len(r.rows) == 2 for r in responses)
        assert len(list(config.output_dir.glob("read-*.sqlite"))) == 1
    finally:
        state.close()


def test_sql_cancellation_settles_before_releasing_admission(tmp_path, monkeypatch):
    import sqlite3
    import threading

    import catalog_worker.query_server as server

    started = threading.Event()
    settled = threading.Event()

    def expensive(root, request, now, cancel):
        started.set()
        with sqlite3.connect(":memory:") as db:
            db.set_progress_handler(lambda: int(cancel.is_set()), 100)
            try:
                db.execute(
                    "WITH RECURSIVE n(x) AS (VALUES(1) UNION ALL SELECT x+1 FROM n WHERE x<1000000000) SELECT sum(x) FROM n"
                ).fetchone()
            finally:
                settled.set()

    monkeypatch.setattr(server, "execute", expensive)
    app = server.create_app(tmp_path, TOKEN)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1"
        ) as http:
            task = asyncio.create_task(
                http.post(
                    "/catalog/v1/query",
                    json=Request(
                        operation="recent", params={"t": "search"}, limit=100
                    ).model_dump(),
                    headers={"Authorization": "Bearer " + TOKEN},
                )
            )
            while not started.is_set():
                await asyncio.sleep(0.005)
            assert app.state.admission.active == 1
            assert sum(app.state.admission.client_active.values()) == 1
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            assert settled.is_set() and app.state.admission.active == 0
            assert not app.state.admission.client_active

    asyncio.run(run())


def test_service_broad_query_remains_a_caller_error(tmp_path):
    from catalog_core.query_client import QueryTooBroad

    async def run():
        async def broad(request):
            return httpx.Response(400, json={"error": "query_too_broad"})

        client = Client(
            "http://127.0.0.1",
            "synthetic",
            TOKEN,
            Cache(tmp_path / "cache"),
            transport=httpx.MockTransport(broad),
        )
        with pytest.raises(QueryTooBroad, match="query_too_broad"):
            await client.fetch(
                Request(operation="titles", params={"t": "search", "q": "b"}), now=NOW
            )
        await client.close()

    asyncio.run(run())


def test_revision_floor_invalidates_other_keys_and_preserves_legacy_floor(tmp_path):
    from catalog_core.protocol import request_digest

    state, config = seed(tmp_path)
    app = create_app(config.output_dir, TOKEN, now=NOW)
    first = Request(operation="recent", params={"t": "search"}, limit=100)
    second = Request(
        operation="recent", params={"t": "search", "maxage": "1"}, limit=100
    )

    async def run():
        cache = Cache(tmp_path / "cache")
        client = Client(
            "http://127.0.0.1",
            "synthetic",
            TOKEN,
            cache,
            transport=httpx.ASGITransport(app=app),
        )
        old = (await client.fetch(first, now=NOW)).response.model_dump()
        await client.http.aclose()

        async def newer(request):
            body = {**old, "revision": 2, "query_digest": request_digest(second)}
            return httpx.Response(200, json=body)

        client.http = httpx.AsyncClient(transport=httpx.MockTransport(newer))
        assert (await client.fetch(second, now=NOW + 1)).response.revision == 2

        async def outage(request):
            return httpx.Response(503)

        await client.http.aclose()
        client.http = httpx.AsyncClient(transport=httpx.MockTransport(outage))
        with pytest.raises(Unavailable):
            await client.fetch(first, now=NOW + 2)
        cache.accept(client.legacy_scope, 3)
        assert client.revision_floor() == 3
        with pytest.raises(Unavailable):
            await client.fetch(second, now=NOW + 2)
        await client.close()

    try:
        asyncio.run(run())
    finally:
        state.close()


def test_verified_publication_repairs_corrupt_identical_read_file(tmp_path):
    from catalog_worker.read_catalog import verify

    state, config = seed(tmp_path)
    try:
        metadata = verify(config.output_dir)
        path = config.output_dir / metadata["database"]
        with path.open("r+b") as stream:
            stream.seek(100)
            value = stream.read(1)
            stream.seek(100)
            stream.write(bytes([value[0] ^ 1]))
        with pytest.raises(ValueError):
            verify(config.output_dir)
        publish(config, state, NOW + 1)
        assert verify(config.output_dir)["revision"] == 2
    finally:
        state.close()


def test_failed_export_or_validation_keeps_last_good_and_removes_staging(
    tmp_path, monkeypatch
):
    import catalog_worker.read_catalog as publication

    state, config = seed(tmp_path)
    pointer = (config.output_dir / "current.json").read_bytes()
    request = Request(operation="recent", params={"t": "tvsearch"}, limit=100)
    from catalog_worker.query_reader import execute

    before = execute(config.output_dir, request, NOW)
    try:
        for name in ("copy", "validate"):
            target = publication if name == "copy" else publication.schema
            original = getattr(target, name)

            def fail(*args, **kwargs):
                raise ValueError("sensitive https://private.invalid?token=secret")

            monkeypatch.setattr(target, name, fail)
            with pytest.raises(ValueError):
                publication.publish(config, state, NOW + 1)
            assert (config.output_dir / "current.json").read_bytes() == pointer
            assert not (config.output_dir / "staging.sqlite").exists()
            after = execute(config.output_dir, request, NOW)
            assert after == before
            monkeypatch.setattr(target, name, original)
    finally:
        state.close()


def test_query_failure_diagnostics_do_not_log_terms_or_credentials(
    tmp_path, monkeypatch, caplog
):
    import sqlite3

    import catalog_worker.query_server as server

    def fail(*args):
        raise sqlite3.OperationalError(
            "secret-query https://player.invalid token=secret"
        )

    monkeypatch.setattr(server, "execute", fail)
    app = server.create_app(tmp_path, TOKEN)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1"
        ) as http:
            response = await http.post(
                "/catalog/v1/query",
                json=Request(
                    operation="titles", params={"t": "search", "q": "private-term"}
                ).model_dump(),
                headers={"Authorization": "Bearer " + TOKEN},
            )
            assert response.status_code == 503

    asyncio.run(run())
    assert "sqlite_error" in caplog.text
    assert all(
        value not in caplog.text
        for value in ["secret-query", "player.invalid", "private-term", TOKEN]
    )


def test_summary_totals_match_sql_for_language_and_cutoff(tmp_path):
    import json

    from catalog_core import schema

    from catalog_worker.query_reader import execute

    state, config = seed(tmp_path)
    try:
        with state.db:
            state.db.execute(
                "UPDATE release SET first_seen_at=? WHERE language='de-dub'",
                (NOW - 2 * 86400,),
            )
        publish(config, state, NOW)
        all_tv = execute(
            config.output_dir,
            Request(
                operation="recent",
                params={"t": "tvsearch"},
                limit=100,
                languages=["de-dub"],
            ),
            NOW,
        )
        narrow = execute(
            config.output_dir,
            Request(
                operation="recent", params={"t": "tvsearch", "maxage": "1"}, limit=100
            ),
            NOW,
        )
        assert all_tv.total == 1 and narrow.total == 1
        assert narrow.rows[0].language == "en-sub"
        metadata = json.loads((config.output_dir / "current.json").read_text())
        metadata["release_summary"][0]["count"] += 1
        with pytest.raises(ValueError, match="invalid release summary"):
            schema.validate(config.output_dir / metadata["database"], metadata)
    finally:
        state.close()


def test_empty_targeted_map_is_explicitly_unresolved(tmp_path):
    from catalog_worker.query_reader import execute

    state, config = seed(tmp_path)
    try:
        tid = state.db.execute("SELECT title_id FROM title").fetchone()[0]
        result = execute(
            config.output_dir,
            Request(
                operation="native", params={"t": "search"}, title_ids=[tid], season=99
            ),
            NOW,
        )
        assert result.total == 0 and result.mapping == "unresolved"
    finally:
        state.close()


def test_admission_caps_operations_clients_and_client_map(tmp_path):
    from catalog_worker.query_server import Admission

    admission = Admission(rate=10_000, burst=10_000)
    for _ in range(4):
        assert admission.enter("10.0.0.1", "native")
    assert admission.client_active["10.0.0.1"] == 4
    assert not admission.enter("10.0.0.2", "native")
    assert admission.enter("10.0.0.2", "titles")
    admission.leave("10.0.0.2", "titles")
    for _ in range(4):
        admission.leave("10.0.0.1", "native")
    assert admission.active == 0 and not admission.client_active

    # A per-source cap applies across operations even when the operation and
    # global caps still have room.
    for operation in ("titles", "titles", "recent", "recent"):
        assert admission.enter("198.51.100.1", operation)
    assert admission.client_active["198.51.100.1"] == Admission.CLIENT_ACTIVE
    assert not admission.enter("198.51.100.1", "native")
    assert admission.enter("198.51.100.2", "native")
    for operation in ("titles", "titles", "recent", "recent"):
        admission.leave("198.51.100.1", operation)
    admission.leave("198.51.100.2", "native")
    assert not admission.client_active

    for index in range(100):
        client = f"192.0.2.{index}"
        assert admission.enter(client, "titles")
        admission.leave(client, "titles")
    assert len(admission.clients) <= Admission.CLIENTS


def test_tampered_pointer_and_symlinked_read_database_are_rejected(tmp_path):
    import json
    import os

    from catalog_worker.query_reader import execute
    from catalog_worker.read_catalog import verify

    state, config = seed(tmp_path)
    root = config.output_dir
    request = Request(operation="recent", params={"t": "search"}, limit=100)
    original = (root / "current.json").read_bytes()
    metadata = json.loads(original)
    try:
        metadata["database"] = "../state/aniworld.to.sqlite"
        (root / "current.json").write_text(json.dumps(metadata))
        with pytest.raises(ValueError, match="invalid read database"):
            execute(root, request, NOW)
        with pytest.raises(ValueError, match="invalid read database"):
            verify(root)

        (root / "current.json").write_bytes(original)
        database = root / json.loads(original)["database"]
        state_file = Path(state.db.execute("PRAGMA database_list").fetchone()[2])
        database.unlink()
        os.symlink(state_file, database)
        with pytest.raises(ValueError, match="unsafe read database"):
            execute(root, request, NOW)
        with pytest.raises(ValueError, match="unsafe read database"):
            verify(root)
    finally:
        state.close()


def test_titles_aliases_and_mappings_use_batched_queries(tmp_path):
    from catalog_worker.query_reader import titles

    state, _config = seed(tmp_path)
    try:
        tid = state.db.execute("SELECT title_id FROM title").fetchone()[0]
        other = identity.title_id("aniworld.to", "/anime/stream/second")
        with state.db:
            state.db.execute(
                "INSERT INTO title VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    other,
                    "/anime/stream/second",
                    "second",
                    "Second",
                    "second",
                    "series",
                    2020,
                    "/anime/stream/second",
                    NOW,
                    "complete",
                ),
            )
        statements = []
        state.db.set_trace_callback(statements.append)
        assert len(titles(state.db, {tid, other}, "aniworld.to")) == 2
        selects = [
            statement
            for statement in statements
            if statement.lstrip().upper().startswith("SELECT")
        ]
        # One title lookup, one alias batch and one mapping batch. The old
        # implementation issued 1 + 2 * len(ids) queries.
        assert len(selects) == 3
    finally:
        state.db.set_trace_callback(None)
        state.close()


def test_empty_targeted_ids_never_reach_sql(tmp_path):
    from catalog_worker.query_reader import titles

    with pytest.raises(ValueError):
        Request(operation="native", params={"t": "search"}, title_ids=[])
    state, _config = seed(tmp_path)
    try:
        statements = []
        state.db.set_trace_callback(statements.append)
        assert titles(state.db, set(), "aniworld.to") == []
        assert not [
            statement
            for statement in statements
            if statement.lstrip().upper().startswith("SELECT")
        ]
    finally:
        state.close()


def test_progress_abort_maps_to_query_deadline(tmp_path, monkeypatch):
    import sqlite3
    import threading

    from catalog_core.json_codec import ContractError

    from catalog_worker.query_reader import execute

    state, config = seed(tmp_path)

    def aborted(*args, **kwargs):
        raise sqlite3.OperationalError("interrupted")

    monkeypatch.setattr("catalog_worker.query_reader.query.query", aborted)
    cancel = threading.Event()
    cancel.set()
    try:
        with pytest.raises(ContractError, match="query_deadline"):
            execute(
                config.output_dir,
                Request(operation="recent", params={"t": "search"}, limit=100),
                NOW,
                cancel,
            )
    finally:
        state.close()


def test_export_index_names_are_quoted():
    from catalog_worker.export import quote_identifier

    assert quote_identifier('odd"index') == '"odd""index"'


def test_maximum_row_page_still_obeys_independent_response_byte_cap(
    tmp_path, monkeypatch
):
    from catalog_core.protocol import MAX_RESPONSE, Response, Row, Title, request_digest

    from catalog_worker import query_server

    # Every field and row is legal on its own; the combined page is deliberately
    # larger than the independent byte budget. It must fail without truncation.
    anchor = "/anime/stream/" + "a" * 940
    title_id = identity.title_id("aniworld.to", anchor)
    title = Title(
        title_id=title_id,
        identity_anchor=anchor,
        slug="a" * 240,
        display_title="A" * 512,
        search_key="a" * 512,
        media_type="series",
        year=2020,
        path=anchor,
        observed_at=NOW,
        detail_status="complete",
    )
    rows = []
    for episode in range(1, 501):
        path = f"{anchor}/staffel-1/episode-{episode}"
        entity_id = identity.entity_id("aniworld.to", path)
        rows.append(
            Row(
                provider="aniworld.to",
                title_id=title_id,
                entity_id=entity_id,
                release_id=identity.release_id("aniworld.to", entity_id, "de-dub"),
                snapshot_digest="0" * 64,
                title_anchor=anchor,
                entity_anchor=path,
                path=path,
                slug=title.slug,
                display_title=title.display_title,
                year=2020,
                kind="episode",
                language="de-dub",
                native_season=1,
                native_episode=episode,
                namespace=None,
                external_id=None,
                season=None,
                episode=None,
                first_seen_at=NOW,
                observed_at=NOW,
            )
        )
    request = Request(
        operation="native", params={"t": "search"}, title_ids=[title_id], limit=500
    )
    response = Response(
        query_digest=request_digest(request),
        source_id="synthetic",
        provider="aniworld.to",
        revision=1,
        snapshot_digest="0" * 64,
        listing_checked_at=NOW,
        offset=0,
        mapping="unresolved",
        titles=[title],
        rows=rows,
        total=500,
    )
    response.check_request(request, "synthetic")
    assert len(response.model_dump_json().encode()) > MAX_RESPONSE
    monkeypatch.setattr(query_server, "execute", lambda *args: response)
    app = create_app(tmp_path, TOKEN, now=NOW)

    async def run():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as http:
            result = await http.post(
                "/catalog/v1/query",
                json=request.model_dump(),
                headers={"Authorization": "Bearer " + TOKEN},
            )
        assert result.status_code == 503
        assert result.json() == {"error": "response_too_large"}
        assert app.state.admission.active == 0
        assert app.state.completed == 0

    asyncio.run(run())
