"""Synthetic Filmo listings and declared movie offers; no live provider proof."""

import json
from dataclasses import replace

import pytest
from catalog_core import identity, schema
from catalog_core.protocol import Request
from catalog_core.providers.aniworld import Link
from catalog_core.providers.filmo import parse

from catalog_worker.aniworld import Page
from catalog_worker.config import LIMITS, Config
from catalog_worker.listing import Links, Traversal
from catalog_worker.query_reader import execute
from catalog_worker.read_catalog import provider_root, publish
from catalog_worker.state import State

NOW = 1_800_000_000


def listing(path: str, next_page: int | None = None) -> bytes:
    next_link = (
        f'<a rel="next" href="/movies?page={next_page}">Next</a>' if next_page else ""
    )
    return (
        '<div class="movie-poster-grid-card"><a href="'
        + path
        + '">Observed Film</a></div>'
        + next_link
    ).encode()


def detail(
    host: str = "VOE",
    label: str = "Deutsch Dub",
    quality_label: str = "1080p",
    second_offer: bool = False,
):
    second = (
        '<div data-provider-chip data-movie-link-id="818" aria-label="FileMoon">'
        '<span class="provider-chip__metadata-tag">720p</span></div>'
        if second_offer
        else ""
    )
    return (
        '<div id="movie-detail-page" data-movie-id="41">'
        "<h1>Observed Film</h1>"
        '<div class="provider-row"><span class="provider-row__lang">'
        + label
        + '</span><div data-provider-chip data-movie-link-id="817" aria-label="'
        + host
        + '"><span class="provider-chip__metadata-tag">'
        + quality_label
        + "</span></div>"
        + second
        + "</div>"
        "</div>"
    ).encode()


def test_corrected_audio_classification_updates_projection_without_rehashing(tmp_path):
    state = State(tmp_path / "filmo.sqlite", "filmo.to")
    try:
        movie = "/movies/film-one"
        state.listing(parse(listing(movie), "listing"), NOW)
        work = state.claim(NOW)
        observed = parse(detail(), "detail", movie)
        old = replace(
            observed,
            offers=tuple(
                {**item, "audio_languages": ["und"]} for item in observed.offers
            ),
        )
        state.detail(work, old, NOW)
        before = dict(state.db.execute("SELECT * FROM release").fetchone())
        assert before["language"] == "und"
        state.detail(work, observed, NOW + 1)
        after = dict(state.db.execute("SELECT * FROM release").fetchone())
        assert after["language"] == "deu"
        assert after["release_id"] == before["release_id"]
        assert after["first_seen_at"] == before["first_seen_at"]
        stored = json.loads(
            state.db.execute("SELECT metadata_json FROM release_metadata").fetchone()[0]
        )
        assert stored["audio_languages"] == ["deu"]
    finally:
        state.close()


def test_listing_checkpoints_more_than_one_hundred_pages(tmp_path):
    state = State(tmp_path / "filmo.sqlite", "filmo.to")
    old_id = state.discover(Link("/movies/previous", "Previously Seen"), NOW - 1)
    state.db.commit()
    traversal = Traversal(state.db, max_pages=1000)
    assert traversal.next_path("/movies") == "/movies"
    page = parse(listing("/movies/film-one", 2), "listing", "/movies")
    assert not traversal.add("/movies", page)
    assert state.db.execute("SELECT count(*) FROM title").fetchone()[0] == 1
    for number in range(2, 103):
        path = f"/movies?page={number}"
        next_page = number + 1 if number < 102 else None
        page = parse(listing("/movies/film-one", next_page), "listing", path)
        complete = traversal.add(path, page)
        if number < 102:
            assert not complete
            assert state.db.execute("SELECT count(*) FROM title").fetchone()[0] == 1
        else:
            assert complete
        if number == 40:
            state.close()
            state = State(tmp_path / "filmo.sqlite", "filmo.to")
            traversal = Traversal(state.db, max_pages=1000)
            assert traversal.next_path("/movies") == "/movies?page=41"
    assert state.meta()["listing_checked_at"] == 0
    assert state.db.execute("SELECT count(*) FROM omissions").fetchone()[0] == 0
    state.listing(
        type(page)(Links(state.db), (), 0, None), NOW, accepted=traversal.clear
    )
    assert state.db.execute("SELECT count(*) FROM title").fetchone()[0] == 2
    assert (
        state.db.execute(
            "SELECT count FROM omissions WHERE kind='title' AND id=?", (old_id,)
        ).fetchone()[0]
        == 1
    )
    state.close()


def test_variant_ids_and_first_seen_survive_metadata_corrections_and_restart(tmp_path):
    filename = tmp_path / "filmo.sqlite"
    state = State(filename, "filmo.to")
    movie_path = "/movies/film-one"
    state.listing(parse(listing(movie_path), "listing", "/movies"), NOW)
    work = state.claim(NOW)
    page = parse(detail(), "detail", movie_path)
    state.detail(work, page, NOW)
    first = dict(state.db.execute("SELECT * FROM release").fetchone())
    metadata_before = json.loads(
        state.db.execute("SELECT metadata_json FROM release_metadata").fetchone()[0]
    )
    assert first["release_id"] == identity.variant_release_id(
        "filmo.to", first["entity_id"], metadata_before["variant_anchor"]
    )
    assert first["language"] == "deu"
    title_id = state.db.execute("SELECT title_id FROM title").fetchone()[0]
    state.db.execute(
        "INSERT INTO canonical_title VALUES(?,?,?,?,?,?,?)",
        (
            identity.mapping_id("filmo.to", title_id, "tmdb-movie", "123"),
            title_id,
            "tmdb-movie",
            "123",
            "tmdb-v3",
            "reviewed",
            NOW,
        ),
    )
    state.discover(Link(movie_path, "Poster/Card Label"), NOW + 1)
    assert (
        state.db.execute(
            "SELECT display_title FROM title WHERE title_id=?", (title_id,)
        ).fetchone()[0]
        == "Observed Film"
    )
    assert (
        state.db.execute(
            "SELECT external_id FROM canonical_title WHERE title_id=?", (title_id,)
        ).fetchone()[0]
        == "123"
    )
    state.close()

    state = State(filename, "filmo.to")
    work = dict(state.db.execute("SELECT * FROM work").fetchone())
    state.detail(
        work,
        parse(detail(quality_label="720p"), "detail", movie_path),
        NOW + 10,
    )
    corrected = dict(state.db.execute("SELECT * FROM release").fetchone())
    assert corrected["release_id"] == first["release_id"]
    assert corrected["first_seen_at"] == NOW
    assert corrected["observed_at"] == NOW + 10
    assert state.db.execute("SELECT count(*) FROM release_metadata").fetchone()[0] == 1
    state.close()


def test_bad_variant_update_rolls_back_entity_and_release_writes(tmp_path):
    state = State(tmp_path / "filmo.sqlite", "filmo.to")
    movie_path = "/movies/film-one"
    state.listing(parse(listing(movie_path), "listing", "/movies"), NOW)
    work = state.claim(NOW)
    valid = parse(detail(), "detail", movie_path)
    state.detail(work, valid, NOW)
    work = dict(state.db.execute("SELECT * FROM work").fetchone())
    stored_metadata = state.db.execute(
        "SELECT metadata_json,available FROM release_metadata"
    ).fetchone()
    broken = parse(detail(), "detail", movie_path)
    invalid_offer = {**broken.offers[0], "host": "unsafe host!?"}
    with pytest.raises(ValueError, match="invalid offer host"):
        state.detail(work, replace(broken, offers=(invalid_offer,)), NOW + 1)
    assert state.db.execute("SELECT count(*) FROM release").fetchone()[0] == 1
    assert tuple(
        state.db.execute(
            "SELECT metadata_json,available FROM release_metadata"
        ).fetchone()
    ) == tuple(stored_metadata)
    state.close()


def test_unavailable_offer_withdrawal_and_reappearance_preserve_history(tmp_path):
    state_dir = tmp_path / "state"
    output_dir = tmp_path / "read"
    state = State(state_dir / "filmo.to.sqlite", "filmo.to")
    movie_path = "/movies/film-one"
    state.listing(parse(listing(movie_path), "listing", "/movies"), NOW)
    state.detail(
        state.claim(NOW),
        parse(detail(second_offer=True), "detail", movie_path),
        NOW,
    )
    original = {
        row["release_id"]: row["first_seen_at"]
        for row in state.db.execute("SELECT * FROM release")
    }
    config = Config(
        {"filmo.to": "https://filmo.to"},
        {"tv": "off", "movie": "off"},
        state_dir,
        output_dir,
        tmp_path / "unused-key",
        "synthetic-filmo",
        "127.0.0.1",
        8080,
        {key: value[0] for key, value in LIMITS.items()},
    )
    try:
        publish(config, state, NOW)
        current_path = provider_root(output_dir, "filmo.to") / "current.json"
        current_before = current_path.read_bytes()
        malformed = b"<html><body><h1>Observed Film</h1><div class=provider-rows>"
        with pytest.raises(ValueError):
            parse(malformed, "detail", movie_path)
        assert current_path.read_bytes() == current_before
        assert (
            state.db.execute(
                "SELECT count(*) FROM release_metadata WHERE available=1"
            ).fetchone()[0]
            == 2
        )

        work = dict(state.db.execute("SELECT * FROM work").fetchone())
        receipt = (
            work["path"],
            NOW - 3600,
            NOW - 10,
            NOW,
            "transport_failure",
            503,
            "timeout",
        )
        state.db.execute("UPDATE work SET failures=3 WHERE path=?", (work["path"],))
        state.db.execute("INSERT INTO work_failure VALUES(?,?,?,?,?,?,?)", receipt)
        state.db.commit()
        work = dict(state.db.execute("SELECT * FROM work").fetchone())
        baseline_content = state.db.execute(
            "SELECT content_generation FROM publication_meta"
        ).fetchone()[0]

        unavailable = Page((), (), 0, "Observed Film", availability="unavailable")
        state.detail(work, unavailable, NOW)
        active = state.db.execute(
            "SELECT count(*) FROM release_metadata WHERE available=1"
        ).fetchone()[0]
        assert active == 0
        assert state.db.execute("SELECT count(*) FROM release").fetchone()[0] == 2
        assert (
            state.db.execute(
                "SELECT count(*) FROM work_failure WHERE path=?", (work["path"],)
            ).fetchone()[0]
            == 1
        )
        assert (
            state.db.execute(
                "SELECT failures FROM work WHERE path=?", (work["path"],)
            ).fetchone()[0]
            == 3
        )
        withdrawn_content = state.db.execute(
            "SELECT content_generation FROM publication_meta"
        ).fetchone()[0]
        assert withdrawn_content == baseline_content + 3

        # A repeated empty unavailable response changes observation clocks but
        # creates no second release-content event.
        state.detail(
            dict(state.db.execute("SELECT * FROM work").fetchone()), unavailable, NOW
        )
        assert (
            state.db.execute(
                "SELECT content_generation FROM publication_meta"
            ).fetchone()[0]
            == withdrawn_content
        )
        with pytest.raises(ValueError, match="invalid Filmo availability"):
            state.detail(
                dict(state.db.execute("SELECT * FROM work").fetchone()),
                replace(unavailable, availability="unknown"),
                NOW,
            )
        assert (
            state.db.execute(
                "SELECT count(*) FROM release_metadata WHERE available=0"
            ).fetchone()[0]
            == 2
        )

        publish(config, state, NOW)
        root = provider_root(output_dir, "filmo.to")
        current = json.loads((root / "current.json").read_text())
        public = schema.connect(root / current["database"])
        try:
            assert (
                public.execute("SELECT count(*) FROM release_data").fetchone()[0] == 0
            )
        finally:
            public.close()
        empty = execute(
            output_dir,
            Request(
                operation="recent",
                provider="filmo.to",
                params={"t": "search"},
                limit=100,
                languages=[],
            ),
            NOW,
        )
        assert empty.total == 0 and not empty.rows

        state.detail(
            dict(state.db.execute("SELECT * FROM work").fetchone()),
            parse(detail(second_offer=True), "detail", movie_path),
            NOW,
        )
        restored = {
            row["release_id"]: row["first_seen_at"]
            for row in state.db.execute("SELECT * FROM release")
        }
        assert restored == original
        assert (
            state.db.execute(
                "SELECT count(*) FROM release_metadata WHERE available=1"
            ).fetchone()[0]
            == 2
        )
        assert (
            state.db.execute(
                "SELECT failures FROM work WHERE path=?", (work["path"],)
            ).fetchone()[0]
            == 0
        )
        assert (
            state.db.execute(
                "SELECT 1 FROM work_failure WHERE path=?", (work["path"],)
            ).fetchone()
            is None
        )
        publish(config, state, NOW)
        current = json.loads((root / "current.json").read_text())
        public = schema.connect(root / current["database"])
        try:
            assert (
                public.execute("SELECT count(*) FROM release_data").fetchone()[0] == 2
            )
        finally:
            public.close()
    finally:
        state.close()


def test_missing_offer_metadata_fails_export_and_keeps_last_good_pointer(tmp_path):
    state_dir = tmp_path / "state"
    output_dir = tmp_path / "read"
    state = State(state_dir / "filmo.to.sqlite", "filmo.to")
    movie_path = "/movies/film-one"
    state.listing(parse(listing(movie_path), "listing", "/movies"), NOW)
    state.detail(state.claim(NOW), parse(detail(), "detail", movie_path), NOW)
    config = Config(
        {"filmo.to": "https://filmo.to"},
        {"tv": "off", "movie": "off"},
        state_dir,
        output_dir,
        tmp_path / "unused-key",
        "synthetic-filmo",
        "127.0.0.1",
        8080,
        {key: value[0] for key, value in LIMITS.items()},
    )
    try:
        publish(config, state, NOW)
        current = provider_root(output_dir, "filmo.to") / "current.json"
        last_good = current.read_bytes()
        state.db.execute("DELETE FROM release_metadata")
        state.db.commit()
        with pytest.raises(
            ValueError,
            match="invalid release language|invalid release metadata storage",
        ):
            publish(config, state, NOW + 1)
        assert current.read_bytes() == last_good
        assert not (provider_root(output_dir, "filmo.to") / "staging.sqlite").exists()
    finally:
        state.close()


def test_corrupt_availability_flag_fails_export_and_preserves_last_good(tmp_path):
    state_dir = tmp_path / "state"
    output_dir = tmp_path / "read"
    state = State(state_dir / "filmo.to.sqlite", "filmo.to")
    movie_path = "/movies/film-one"
    state.listing(parse(listing(movie_path), "listing", "/movies"), NOW)
    state.detail(state.claim(NOW), parse(detail(), "detail", movie_path), NOW)
    config = Config(
        {"filmo.to": "https://filmo.to"},
        {"tv": "off", "movie": "off"},
        state_dir,
        output_dir,
        tmp_path / "unused-key",
        "synthetic-filmo",
        "127.0.0.1",
        8080,
        {key: value[0] for key, value in LIMITS.items()},
    )
    try:
        publish(config, state, NOW)
        current = provider_root(output_dir, "filmo.to") / "current.json"
        last_good = current.read_bytes()
        state.db.execute("PRAGMA ignore_check_constraints=ON")
        state.db.execute("UPDATE release_metadata SET available=2")
        state.db.commit()
        with pytest.raises(ValueError, match="invalid release availability"):
            publish(config, state, NOW + 1)
        assert current.read_bytes() == last_good
        assert not (provider_root(output_dir, "filmo.to") / "staging.sqlite").exists()
    finally:
        state.close()


def test_schema3_publication_and_query_return_validated_variant_metadata(tmp_path):
    state_dir = tmp_path / "state"
    output_dir = tmp_path / "read"
    state = State(state_dir / "filmo.to.sqlite", "filmo.to")
    movie_path = "/movies/film-one"
    state.listing(parse(listing(movie_path), "listing", "/movies"), NOW)
    state.detail(
        state.claim(NOW),
        parse(detail(second_offer=True), "detail", movie_path),
        NOW,
    )
    config = Config(
        {"filmo.to": "https://filmo.to"},
        {"tv": "off", "movie": "off"},
        state_dir,
        output_dir,
        tmp_path / "unused-key",
        "synthetic-filmo",
        "127.0.0.1",
        8080,
        {key: value[0] for key, value in LIMITS.items()},
    )
    try:
        publish(config, state, NOW)
        root = provider_root(output_dir, "filmo.to")
        current = json.loads((root / "current.json").read_text())
        assert current["catalog_schema_version"] == 3
        assert current["identity_version"] == 2
        db = schema.connect(root / current["database"])
        try:
            release = dict(db.execute("SELECT * FROM release_data").fetchone())
            assert release["metadata"]
            assert release["variant_anchor"]
        finally:
            db.close()
        response = execute(
            output_dir,
            Request(
                operation="recent",
                provider="filmo.to",
                params={"t": "search"},
                limit=100,
                languages=[],
            ),
            NOW,
        )
        assert response.rows[0].release_metadata["native_id"] == "817"
        assert response.rows[0].variant_anchor
        assert len(response.rows) == 2
        assert {row.release_metadata["native_id"] for row in response.rows} == {
            "817",
            "818",
        }
        # Metadata corrections participate in the publication journal and
        # become visible through query serving after the next safe export.
        generation = state.db.execute(
            "SELECT generation FROM publication_meta"
        ).fetchone()[0]
        work = dict(state.db.execute("SELECT * FROM work").fetchone())
        state.detail(
            work,
            parse(
                detail(quality_label="720p", second_offer=True), "detail", movie_path
            ),
            NOW + 1,
        )
        assert (
            state.db.execute("SELECT generation FROM publication_meta").fetchone()[0]
            > generation
        )
        publish(config, state, NOW + 1)
        updated = execute(
            output_dir,
            Request(
                operation="recent",
                provider="filmo.to",
                params={"t": "search"},
                limit=100,
                languages=[],
            ),
            NOW + 1,
        )
        assert (
            next(
                row
                for row in updated.rows
                if row.release_metadata["native_id"] == "817"
            ).release_metadata["quality"]["resolution"]
            == 720
        )
    finally:
        state.close()


def test_old_provider_identity_and_private_schema_stay_at_v7(tmp_path):
    filename = tmp_path / "aniworld.to.sqlite"
    state = State(filename, "aniworld.to")
    state.listing(
        type("Page", (), {"links": (Link("/anime/stream/example", "Example"),)})(), NOW
    )
    title_id = state.db.execute("SELECT title_id FROM title").fetchone()[0]
    assert title_id == identity.title_id("aniworld.to", "/anime/stream/example")
    assert state.db.execute("SELECT version FROM worker_schema").fetchone()[0] == 7
    assert not state.db.execute(
        "SELECT 1 FROM sqlite_schema WHERE name='release_metadata'"
    ).fetchone()
    state.close()
