"""Filmo host availability is filtered without mutating the published offers."""

import asyncio
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import httpx
from catalog_core import identity, query
from catalog_core.protocol import Request
from catalog_core.providers.filmo import parse
from catalog_core.query_client import Cache, Client

WORKER_SOURCE = Path(__file__).resolve().parents[4] / "catalog-worker" / "src"
if str(WORKER_SOURCE) not in sys.path:
    sys.path.insert(0, str(WORKER_SOURCE))

from catalog_worker.config import LIMITS, Config  # noqa: E402
from catalog_worker.query_server import create_app as create_query_app  # noqa: E402
from catalog_worker.read_catalog import publish  # noqa: E402
from catalog_worker.state import State  # noqa: E402

from app.catalog.query_local import Search  # noqa: E402

NOW = 1_800_000_000
TOKEN = "synthetic-filmo-host-filter-token"


def _detail() -> bytes:
    offers = []
    for native_id, host in (("41", "VOE"), ("42", "Byse"), ("43", "Filemoon")):
        offers.append(
            '<div class="provider-row"><span class="provider-row__lang">English Dub</span>'
            f'<div data-provider-chip data-movie-link-id="{native_id}" '
            f'aria-label="{host}"><span class="provider-chip__metadata-tag">720p</span></div>'
            "</div>"
        )
    return (
        '<div id="movie-detail-page"><h1>Host Filter Feature</h1>'
        + "".join(offers)
        + "</div>"
    ).encode()


def _catalog(tmp_path):
    state_dir, output_dir = tmp_path / "state", tmp_path / "read"
    state_dir.mkdir()
    state = State(state_dir / "filmo.to.sqlite", "filmo.to")
    title_path = "/movies/host-filter-feature"
    state.listing(
        parse(
            f'<a class="movie-poster-grid-card" href="{title_path}">Feature</a>'.encode(),
            "listing",
            "/movies",
        ),
        NOW,
    )
    state.detail(state.claim(NOW), parse(_detail(), "detail", title_path), NOW)
    config = Config(
        {"filmo.to": "https://filmo.to"},
        {"tv": "off", "movie": "off"},
        state_dir,
        output_dir,
        tmp_path / "unused-key",
        "synthetic-filmo-hosts",
        "127.0.0.1",
        8080,
        {key: value[0] for key, value in LIMITS.items()},
    )
    publish(config, state, NOW)
    return state, config, output_dir, title_path


def test_search_filters_unsupported_hosts_before_local_totals_and_pagination(tmp_path):
    state, config, output_dir, title_path = _catalog(tmp_path)
    app = create_query_app(output_dir, TOKEN, now=NOW)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    jobs_database = tmp_path / "jobs.sqlite"
    with closing(sqlite3.connect(jobs_database)) as db, db:
        db.execute(
            "CREATE TABLE catalog_override(id TEXT,provider TEXT,title_id TEXT,entity_id TEXT,namespace TEXT,body TEXT,version INTEGER,created_at INTEGER,updated_at INTEGER)"
        )

    async def run():
        client = Client(
            "http://127.0.0.1",
            "synthetic-filmo-hosts",
            TOKEN,
            Cache(tmp_path / "cache.sqlite"),
            transport=httpx.ASGITransport(app=app),
        )
        sent_requests = []
        fetch = client.fetch

        async def capture_request(request, *args, **kwargs):
            sent_requests.append(request)
            return await fetch(request, *args, **kwargs)

        client.fetch = capture_request
        search = Search(client, jobs_database, scratch, "filmo.to")
        try:
            first, first_total, _ = await search.search(
                {"t": "movie", "q": "Host Filter", "limit": "1", "offset": "0"},
                now=NOW,
            )
            second, second_total, _ = await search.search(
                {"t": "movie", "q": "Host Filter", "limit": "1", "offset": "1"},
                now=NOW,
            )
            assert first_total == second_total == 2
            assert len(first) == len(second) == 1
            assert {
                first[0]["release_metadata"]["host"],
                second[0]["release_metadata"]["host"],
            } == {
                "VOE",
                "Byse",
            }

            recent_first, recent_total, _ = await search.search(
                {"t": "movie", "limit": "1", "offset": "0"}, now=NOW
            )
            recent_second, recent_second_total, _ = await search.search(
                {"t": "movie", "limit": "1", "offset": "1"}, now=NOW
            )
            assert recent_total == recent_second_total == 2
            assert len(recent_first) == len(recent_second) == 1
            assert {
                recent_first[0]["release_metadata"]["host"],
                recent_second[0]["release_metadata"]["host"],
            } == {"VOE", "Byse"}
            recent_requests = [
                request for request in sent_requests if request.operation == "recent"
            ]
            assert len(recent_requests) == 2
            assert all(
                request.offer_hosts == ["Byse", "VOE"] for request in recent_requests
            )

            # Unfiltered protocol reads keep the source catalog's third offer.
            raw = await client.fetch(
                Request(
                    operation="native",
                    provider="filmo.to",
                    params={"t": "search"},
                    title_ids=[identity.title_id("filmo.to", title_path)],
                    limit=100,
                    languages=[],
                ),
                now=NOW,
            )
            assert raw.response.total == 3
            assert {row.release_metadata["host"] for row in raw.response.rows} == {
                "VOE",
                "Byse",
                "Filemoon",
            }

            # The API's local projection applies the same predicate if it is
            # handed a raw response, before its count and page are computed.
            parsed = query.parse({"t": "movie", "q": "Host Filter", "limit": "1"})
            local_first, local_total, _ = await search.project(
                [raw.response],
                parsed,
                [],
                now=NOW,
                modes=("download",),
                languages=None,
                anime_category=5070,
                movie_category=2000,
            )
            assert local_total == 2 and len(local_first) == 1
            assert local_first[0]["release_metadata"]["host"] in {"VOE", "Byse"}
        finally:
            await client.close()

    try:
        asyncio.run(run())
    finally:
        state.close()
