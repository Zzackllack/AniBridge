"""The query reader filters selectable hosts while retaining raw source rows."""

from catalog_core.protocol import Request
from catalog_core.providers.filmo import parse

from catalog_worker.config import LIMITS, Config
from catalog_worker.query_reader import execute
from catalog_worker.read_catalog import publish
from catalog_worker.state import State

NOW = 1_800_000_000


def test_query_reader_applies_filmo_host_filter_and_keeps_raw_offers(tmp_path):
    state_dir, output_dir = tmp_path / "state", tmp_path / "read"
    state_dir.mkdir()
    state = State(state_dir / "filmo.to.sqlite", "filmo.to")
    title_path = "/movies/host-filter"
    state.listing(
        parse(
            b'<a class="movie-poster-grid-card" href="/movies/host-filter">Feature</a>',
            "listing",
            "/movies",
        ),
        NOW,
    )
    detail = b"""<h1>Host Filter</h1>
      <div class="provider-row"><span class="provider-row__lang">English Dub</span>
        <div data-provider-chip data-movie-link-id="41" aria-label="VOE"></div>
      </div>
      <div class="provider-row"><span class="provider-row__lang">English Dub</span>
        <div data-provider-chip data-movie-link-id="42" aria-label="Byse"></div>
      </div>
      <div class="provider-row"><span class="provider-row__lang">English Dub</span>
        <div data-provider-chip data-movie-link-id="43" aria-label="Filemoon"></div>
      </div>"""
    state.detail(state.claim(NOW), parse(detail, "detail", title_path), NOW)
    config = Config(
        {"filmo.to": "https://filmo.to"},
        {"tv": "off", "movie": "off"},
        state_dir,
        output_dir,
        tmp_path / "unused-key",
        "synthetic-filmo-query",
        "127.0.0.1",
        8080,
        {key: value[0] for key, value in LIMITS.items()},
    )
    try:
        publish(config, state, NOW)
        title_id = state.db.execute(
            "SELECT title_id FROM title WHERE path=?", (title_path,)
        ).fetchone()[0]
        filtered = execute(
            output_dir,
            Request(
                operation="recent",
                provider="filmo.to",
                params={"t": "movie"},
                limit=100,
                languages=[],
                offer_hosts=["VOE", "Byse"],
            ),
            NOW,
        )
        assert filtered.total == 2
        assert {row.release_metadata["host"] for row in filtered.rows} == {
            "VOE",
            "Byse",
        }

        raw = execute(
            output_dir,
            Request(
                operation="native",
                provider="filmo.to",
                params={"t": "search"},
                title_ids=[title_id],
                limit=100,
                languages=[],
            ),
            NOW,
        )
        assert raw.total == 3
        assert {row.release_metadata["host"] for row in raw.rows} == {
            "VOE",
            "Byse",
            "Filemoon",
        }
    finally:
        state.close()
