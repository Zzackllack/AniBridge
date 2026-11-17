"""End-to-end Filmo Collector path through its supervised parser child."""

import asyncio
import json
import sys
from pathlib import Path

import pytest
from catalog_core.protocol import Request
from catalog_core.providers.transport import Fetch

from catalog_worker.collector import Collector
from catalog_worker.config import LIMITS, Config
from catalog_worker.aniworld import Link
from catalog_worker.query_reader import execute
from catalog_worker.read_catalog import publish
from catalog_worker.state import State
from catalog_worker.transactions import atomic

pytestmark = pytest.mark.skipif(
    sys.platform != "linux",
    reason="Collector parser child resource enforcement requires Linux",
)

ORIGIN = "https://filmo.fixture"
NOW = 1_800_000_000
MOVIE = "/movies/the-example-film"
PLAYER_TOKEN = "do-not-persist-this-player-token"

LISTING_ONE = (
    '<a class="movie-poster-grid-card" '
    f'href="{ORIGIN}{MOVIE}">Example</a>'
    f'<a rel="next" href="{ORIGIN}/movies?page=2">Next</a>'
).encode()
LISTING_TWO = (
    f'<a class="movie-poster-grid-card" href="{ORIGIN}{MOVIE}">Example</a>'
).encode()
DETAIL = (
    '<div id="movie-detail-page" data-movie-id="41">'
    "<h1>Example Feature</h1>"
    '<div class="provider-row"><span class="provider-row__lang">Deutsch Dub</span>'
    '<div data-provider-chip data-movie-link-id="817" aria-label="VOE" '
    f'data-player-url="https://player.fixture/?token={PLAYER_TOKEN}">'
    '<span class="provider-chip__metadata-tag">1080p BluRay</span></div>'
    '<div data-provider-chip data-movie-link-id="818" aria-label="FileMoon">'
    '<span class="provider-chip__metadata-tag">720p</span></div>'
    "</div></div>"
).encode()


def test_filmo_collector_checkpoint_child_persistence_and_query(tmp_path: Path) -> None:
    state_path = tmp_path / "state" / "filmo.to.sqlite"
    state_path.parent.mkdir()
    output_dir = tmp_path / "read"
    limits = {key: value[0] for key, value in LIMITS.items()}
    limits["provider_request_interval_s"] = 1
    config = Config(
        {"filmo.to": ORIGIN},
        {"tv": "off", "movie": "off"},
        state_path.parent,
        output_dir,
        tmp_path / "unused-key",
        "filmo-collector-integration",
        "127.0.0.1",
        8080,
        limits,
    )
    pages = {
        ("/movies", None): LISTING_ONE,
        ("/movies", (("page", "2"),)): LISTING_TWO,
        (MOVIE, None): DETAIL,
    }
    calls: list[tuple[str, dict]] = []

    async def fetch(origin: str, path: str, **options) -> Fetch:
        assert origin == ORIGIN
        query = tuple(sorted(options.get("query", {}).items())) or None
        calls.append((path, dict(options.get("query", {}))))
        await options["before_request"]()
        return Fetch("ok", pages[(path, query)])

    clock = NOW
    state = State(state_path, "filmo.to")
    collector = Collector(config, state, fetcher=fetch, clock=lambda: clock)
    try:
        first = collector.prepare()
        assert first and first.listing and first.path == "/movies"
        collector.apply(asyncio.run(collector.collect(first)))
        assert (
            state.db.execute("SELECT listing_checked_at FROM worker_meta").fetchone()[0]
            == 0
        )

        # Reopen after the first page to exercise the durable next-page checkpoint.
        state.close()
        state = State(state_path, "filmo.to")
        clock += 2
        collector = Collector(config, state, fetcher=fetch, clock=lambda: clock)
        second = collector.prepare()
        assert second and second.listing and second.path == "/movies?page=2"
        collector.apply(asyncio.run(collector.collect(second)))
        assert (
            state.db.execute("SELECT listing_checked_at FROM worker_meta").fetchone()[0]
            == clock
        )
        assert state.db.execute("SELECT count(*) FROM title").fetchone()[0] == 1

        clock += 2
        detail_plan = collector.prepare()
        assert detail_plan and not detail_plan.listing and detail_plan.path == MOVIE
        parsed = asyncio.run(collector.collect(detail_plan))
        assert parsed.outcome == "ok" and parsed.page is not None
        assert parsed.page.title == "Example Feature"
        assert {offer["native_id"] for offer in parsed.page.offers} == {"817", "818"}
        assert PLAYER_TOKEN not in json.dumps(parsed.page.offers)
        collector.apply(parsed)

        first_seen = {
            row["release_id"]: row["first_seen_at"]
            for row in state.db.execute("SELECT * FROM release")
        }
        assert len(first_seen) == 2
        persisted = [
            row[0]
            for row in state.db.execute("SELECT metadata_json FROM release_metadata")
        ]
        assert len(persisted) == 2 and all(
            PLAYER_TOKEN not in item for item in persisted
        )

        publish(config, state, clock)
        response = execute(
            output_dir,
            Request(
                operation="recent",
                provider="filmo.to",
                params={"t": "search"},
                limit=100,
                languages=[],
            ),
            clock,
        )
        assert {row.release_metadata["native_id"] for row in response.rows} == {
            "817",
            "818",
        }
        assert all(row.variant_anchor for row in response.rows)
        assert calls == [
            ("/movies", {}),
            ("/movies", {"page": "2"}),
            (MOVIE, {}),
        ]

        bad_details = (
            DETAIL.replace(
                b'<span class="provider-row__lang">Deutsch Dub</span>', b"", 1
            ),
            DETAIL.replace(b'aria-label="VOE"', b"", 1),
            DETAIL.removesuffix(b"</div></div>"),
            DETAIL.replace(
                b'<div id="movie-detail-page" data-movie-id="41">',
                b'<html><body><div id="movie-detail-page" data-movie-id="41">'
                b'<div class="provider-rows">',
                1,
            ).removesuffix(b"</div></div>")
            + b"</div></body></html>",
            (
                b'<div id="movie-detail-page" data-movie-id="41">'
                b'<h1>Example Feature</h1><div class="provider-rows"></div></div>'
            ),
        )
        previous_offers = [
            tuple(row)
            for row in state.db.execute(
                "SELECT r.release_id,r.first_seen_at,m.available "
                "FROM release r JOIN release_metadata m USING(release_id) "
                "ORDER BY r.release_id"
            )
        ]
        for attempt, bad_detail in enumerate(bad_details, start=1):
            due = state.db.execute(
                "SELECT due FROM work WHERE path=?", (MOVIE,)
            ).fetchone()[0]
            clock = max(clock + 2, due)
            pages[(MOVIE, None)] = bad_detail
            retry_plan = collector.prepare(listing_allowed=False, signal_allowed=False)
            assert retry_plan and retry_plan.work and retry_plan.path == MOVIE
            failed = asyncio.run(collector.collect(retry_plan))
            assert failed.outcome == "unexpected_structure" and failed.page is None
            collector.apply(failed)

            current_offers = [
                tuple(row)
                for row in state.db.execute(
                    "SELECT r.release_id,r.first_seen_at,m.available "
                    "FROM release r JOIN release_metadata m USING(release_id) "
                    "ORDER BY r.release_id"
                )
            ]
            assert current_offers == previous_offers
            work = state.db.execute(
                "SELECT failures,due,lease_until FROM work WHERE path=?", (MOVIE,)
            ).fetchone()
            assert work["failures"] == attempt
            assert work["due"] > clock
            assert work["lease_until"] == 0
            receipt = state.db.execute(
                "SELECT last_failed_at,outcome FROM work_failure WHERE path=?",
                (MOVIE,),
            ).fetchone()
            assert tuple(receipt) == (clock, "unexpected_structure")
        assert calls[-3:] == [(MOVIE, {}), (MOVIE, {}), (MOVIE, {})]

        state.close()
        state = State(state_path, "filmo.to")
        assert {
            row["release_id"]: row["first_seen_at"]
            for row in state.db.execute("SELECT * FROM release")
        } == first_seen
    finally:
        state.close()


def test_incomplete_listing_wrapper_keeps_last_good_inventory(tmp_path: Path) -> None:
    state_path = tmp_path / "state" / "filmo.to.sqlite"
    state_path.parent.mkdir()
    limits = {key: value[0] for key, value in LIMITS.items()}
    limits["provider_request_interval_s"] = 1
    config = Config(
        {"filmo.to": ORIGIN},
        {"tv": "off", "movie": "off"},
        state_path.parent,
        tmp_path / "read",
        tmp_path / "unused-key",
        "filmo-incomplete-listing",
        "127.0.0.1",
        8080,
        limits,
    )
    state = State(state_path, "filmo.to")
    with atomic(state.db):
        state.discover(Link("/movies/retained-film", "Retained Film"), NOW)

    body = (
        b'<div class="movie-poster-grid-card"><a href="/movies/new-film">New Film</a>'
    )

    async def fetch(_origin: str, _path: str, **options) -> Fetch:
        await options["before_request"]()
        return Fetch("ok", body)

    collector = Collector(config, state, fetcher=fetch, clock=lambda: NOW)
    try:
        plan = collector.prepare(signal_allowed=False)
        assert plan and plan.listing and plan.path == "/movies"
        ready = asyncio.run(collector.collect(plan))
        assert ready.outcome == "unexpected_structure" and ready.page is None
        collector.apply(ready)

        assert state.db.execute("SELECT count(*) FROM title").fetchone()[0] == 1
        assert (
            state.db.execute("SELECT listing_checked_at FROM worker_meta").fetchone()[0]
            == 0
        )
        assert state.db.execute("SELECT count(*) FROM omissions").fetchone()[0] == 0
        assert tuple(
            state.db.execute("SELECT path,complete FROM listing_page").fetchone()
        ) == ("/movies", 0)
    finally:
        state.close()
