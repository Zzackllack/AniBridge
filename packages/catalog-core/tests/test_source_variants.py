"""Synthetic selections prove preservation, not provider availability or accuracy."""

import copy
import sqlite3
from contextlib import contextmanager

import pytest
from catalog_core import identity, magnet, query, release_metadata, schema
from catalog_core.compact import Writer, release_summary
from catalog_core.json_codec import ContractError, dumps
from catalog_core.manifest import TABLE_LIMITS
from catalog_core.protocol import Request, Response, Row, Title, request_digest

NOW = 1800000000
PATH = "/movies/example"


def offer(native="17", audio="deu", resolution=720, host="Byse"):
    return {
        "variant_anchor": f"{native}:{audio}",
        "native_id": native,
        "host": host,
        "language_label": "Deutsch" if audio == "deu" else "JPN",
        "audio_languages": [audio],
        "subtitle_languages": None,
        "audio_role": "unknown",
        "subtitle_mode": "unknown",
        "quality": {
            "labels": ["BluRay", f"{resolution}p"],
            "source": "bluray",
            "resolution": resolution,
        },
    }


def catalog(tmp_path, *, include_dual_audio=False, include_unusable_host=False):
    path = tmp_path / "variants.sqlite"
    db = schema.create(path, 3)
    writer = Writer(db, 3)
    tid, eid = identity.title_id("filmo.to", PATH), identity.entity_id("filmo.to", PATH)
    offers = [offer(), offer("18", resolution=1080), offer("19", "jpn")]
    offers[2].update(subtitle_languages=["deu"], subtitle_mode="hard")
    if include_dual_audio:
        dual = offer("20", "eng")
        dual.update(
            variant_anchor="20:dual",
            language_label="English Dub + Japanese Dub",
            audio_languages=["eng", "jpn"],
        )
        offers.append(dual)
    if include_unusable_host:
        offers.append(offer("21", host="Filemoon"))
    with db:
        writer.insert("catalog", (1, "filmo.to", 3, 2, NOW))
        writer.insert(
            "title",
            (
                tid,
                PATH,
                "example",
                "Example",
                "example",
                "movie",
                2020,
                PATH,
                NOW,
                "complete",
            ),
        )
        writer.insert(
            "entity", (eid, tid, PATH, "movie", None, None, "Example", PATH, NOW)
        )
        for item in offers:
            writer.insert(
                "release",
                (
                    identity.variant_release_id(
                        "filmo.to", eid, item["variant_anchor"]
                    ),
                    eid,
                    release_metadata.language(item),
                    NOW - 100,
                    NOW,
                    item["variant_anchor"],
                    dumps(item).decode(),
                ),
            )
    counts = {
        table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in TABLE_LIMITS
    }
    summary = release_summary(db)
    db.close()
    payload = {
        "provider": "filmo.to",
        "catalog_schema_version": 3,
        "identity_version": 2,
        "published_at": NOW,
        "listing_checked_at": NOW,
        "counts": counts,
        "coverage": {"details": "complete", "mappings": "partial"},
        "release_summary": summary,
        "artifact": {"sqlite_sha256": "0" * 64},
    }
    return path, payload


def flat_store(tmp_path, source_path, release_count):
    """Build the API's bounded flat Filmo projection for local filtering."""
    path = tmp_path / "local-filmo.sqlite"
    db = sqlite3.connect(path)
    db.executescript(schema.DDL_V3_FLAT)
    db.executescript(
        "ALTER TABLE release ADD COLUMN variant_anchor TEXT;"
        "ALTER TABLE release ADD COLUMN metadata TEXT;"
    )
    with schema.connect(source_path) as source, db:
        db.execute("INSERT INTO catalog VALUES(1,'filmo.to',3,2,?)", (NOW,))
        for table in ("title", "entity", "release"):
            records = [tuple(row) for row in source.execute(f"SELECT * FROM {table}")]
            db.executemany(
                f"INSERT INTO {table} VALUES({','.join('?' for _ in records[0])})",
                records,
            )
    db.close()
    return Store(
        path,
        {
            "provider": "filmo.to",
            "catalog_schema_version": 1,
            "artifact": {"sqlite_sha256": "0" * 64},
            "counts": {"release": release_count},
        },
    )


class Store:
    providers = ("filmo.to",)

    def __init__(self, path, payload):
        self.path, self.payload = path, payload

    @contextmanager
    def acquire(self):
        db = schema.connect(self.path)
        try:
            yield {"filmo.to": (db, self.payload)}, None
        finally:
            db.close()


@pytest.mark.parametrize("flat", [False, True])
@pytest.mark.parametrize("mapped", [False, True])
def test_movie_mapping_status_does_not_claim_unmapped_offers_are_resolved(
    tmp_path, flat, mapped
):
    path, payload = catalog(tmp_path)
    store = flat_store(tmp_path, path, 3) if flat else Store(path, payload)
    if mapped:
        tid = identity.title_id("filmo.to", PATH)
        with sqlite3.connect(store.path) as db:
            Writer(db, 1 if flat else 3).insert(
                "canonical_title",
                (
                    identity.mapping_id("filmo.to", tid, "tmdb-movie", "123"),
                    tid,
                    "tmdb-movie",
                    "123",
                    "synthetic-v1",
                    "reviewed",
                    NOW,
                ),
            )

    rows, total, headers = query.query(store, query.parse({"t": "movie"}), now=NOW)

    assert total == len(rows) == 3
    assert headers.get("X-AniBridge-Mapping", "resolved") == (
        "resolved" if mapped else "partial"
    )


def test_same_audio_quality_variants_and_subtitles_survive_validation_and_pagination(
    tmp_path,
):
    path, payload = catalog(tmp_path)
    assert schema.validate(path, payload)["release"] == 3
    store = Store(path, payload)
    rows, total, _ = query.query(
        store, query.parse({"t": "movie", "q": "Example", "limit": "2"}), now=NOW
    )
    tail, tail_total, _ = query.query(
        store,
        query.parse({"t": "movie", "q": "Example", "limit": "2", "offset": "2"}),
        now=NOW,
    )
    combined = rows + tail
    assert total == tail_total == 3 and len(combined) == 3
    assert len({r["release_id"] for r in combined}) == 3
    assert sorted(r["release_metadata"]["quality"]["resolution"] for r in combined) == [
        720,
        720,
        1080,
    ]
    japanese = next(r for r in combined if r["language"] == "jpn")
    assert japanese["release_metadata"]["subtitle_languages"] == ["deu"]
    for row in combined:
        wire = Row.model_validate(
            {k: v for k, v in row.items() if k not in {"mode", "category"}}
        )
        grab = {name: row[name] for name in magnet.PAYLOAD_FIELDS - {"canonical"}}
        grab.update(
            canonical=None,
            variant_anchor=wire.variant_anchor,
            release_metadata=wire.release_metadata,
        )
        encoded = magnet.encode(grab, "Example")
        assert "ab_v=3" in encoded
        _, decoded, _ = magnet.decode(encoded)
        assert decoded == grab
        with pytest.raises(ContractError, match="version/provider"):
            magnet.decode(encoded.replace("ab_v=3", "ab_v=2"))


def test_source_identity_excludes_quality_and_token_changes_but_separates_native_choices():
    eid = identity.entity_id("filmo.to", PATH)
    first, second = offer(), offer("18")
    before = identity.variant_release_id("filmo.to", eid, first["variant_anchor"])
    first["quality"].update(resolution=1080, labels=["WEB", "1080p"], source="web")
    assert (
        identity.variant_release_id("filmo.to", eid, first["variant_anchor"]) == before
    )
    assert (
        identity.variant_release_id("filmo.to", eid, second["variant_anchor"]) != before
    )


def test_recent_summary_counts_all_filmo_languages_and_explicit_audio_filter(tmp_path):
    path, payload = catalog(tmp_path)
    assert schema.validate(path, payload)["release"] == 3
    store = Store(path, payload)
    parsed = query.parse({"t": "movie"})
    rows, total, _ = query.query(store, parsed, now=NOW)
    assert total == len(rows) == 3
    rows, total, _ = query.query(
        store, parsed, now=NOW, languages={"filmo.to": {"jpn"}}
    )
    assert total == len(rows) == 1 and rows[0]["language"] == "jpn"


def test_multiaudio_offers_match_any_requested_track_before_count_and_page(tmp_path):
    path, payload = catalog(tmp_path, include_dual_audio=True)
    store = Store(path, payload)
    parsed = query.parse({"t": "movie", "limit": "1"})
    english, english_total, _ = query.query(
        store, parsed, now=NOW, languages={"filmo.to": {"eng"}}
    )
    assert english_total == len(english) == 1
    dual = english[0]
    assert dual["language"] == "mul"
    assert dual["release_metadata"]["native_id"] == "20"

    local, local_total, _ = query.query(
        flat_store(tmp_path, path, 4),
        parsed,
        now=NOW,
        languages={"filmo.to": {"eng"}},
    )
    assert local_total == len(local) == 1
    assert local[0]["release_metadata"]["native_id"] == "20"

    japanese, japanese_total, _ = query.query(
        store, parsed, now=NOW, languages={"filmo.to": {"jpn"}}
    )
    japanese_tail, tail_total, _ = query.query(
        store,
        query.parse({"t": "movie", "limit": "1", "offset": "1"}),
        now=NOW,
        languages={"filmo.to": {"jpn"}},
    )
    assert japanese_total == tail_total == 2
    assert len(japanese) == len(japanese_tail) == 1
    assert {
        row["release_metadata"]["native_id"] for row in japanese + japanese_tail
    } == {"19", "20"}

    request = Request(
        operation="recent",
        provider="filmo.to",
        params={"t": "movie"},
        limit=100,
        languages=["eng"],
    )
    wire_row = Row.model_validate(
        {key: value for key, value in dual.items() if key in Row.model_fields}
    )
    title = Title(
        provider="filmo.to",
        title_id=dual["title_id"],
        identity_anchor=dual["title_anchor"],
        slug=dual["slug"],
        display_title=dual["display_title"],
        search_key=identity.search_key(dual["display_title"]),
        media_type="movie",
        year=dual["year"],
        path=dual["path"],
        observed_at=dual["observed_at"],
        detail_status="complete",
    )
    response = Response(
        query_digest=request_digest(request),
        source_id="variants",
        provider="filmo.to",
        revision=1,
        snapshot_digest=dual["snapshot_digest"],
        listing_checked_at=NOW,
        total=1,
        offset=0,
        mapping="unresolved",
        rows=[wire_row],
        titles=[title],
    )
    response.check_request(request, "variants")


def test_filmo_host_allowlist_filters_before_counts_pagination_and_response_validation(
    tmp_path,
):
    path, payload = catalog(tmp_path, include_unusable_host=True)
    store = Store(path, payload)
    parsed = query.parse({"t": "movie", "limit": "1"})
    raw_first, raw_total, _ = query.query(store, parsed, now=NOW)
    assert raw_total == 4
    assert len(raw_first) == 1
    first, total, _ = query.query(store, parsed, now=NOW, offer_hosts={"VOE", "Byse"})
    tail, tail_total, _ = query.query(
        store,
        query.parse({"t": "movie", "limit": "1", "offset": "1"}),
        now=NOW,
        offer_hosts={"VOE", "Byse"},
    )
    assert total == tail_total == 3
    assert len(first) == len(tail) == 1
    assert all(
        row["release_metadata"]["host"] in {"VOE", "Byse"} for row in first + tail
    )

    local, local_total, _ = query.query(
        flat_store(tmp_path, path, 4),
        parsed,
        now=NOW,
        offer_hosts={"VOE", "Byse"},
    )
    assert local_total == 3
    assert local and all(
        row["release_metadata"]["host"] in {"VOE", "Byse"} for row in local
    )

    request = Request(
        operation="recent",
        provider="filmo.to",
        params={"t": "movie"},
        limit=100,
        languages=[],
        offer_hosts=["VOE", "Byse"],
    )
    assert request.wire()["offer_hosts"] == ["VOE", "Byse"]
    assert (
        "offer_hosts"
        not in Request(
            operation="recent",
            params={"t": "movie"},
            provider="aniworld.to",
            limit=100,
        ).wire()
    )

    raw_rows, _, _ = query.query(store, parsed, now=NOW)
    unsupported = next(
        row for row in raw_rows if row["release_metadata"]["host"] == "Filemoon"
    )
    with pytest.raises(ValueError, match="unexpected offer host"):
        response_row = Row.model_validate(
            {
                key: value
                for key, value in unsupported.items()
                if key in Row.model_fields
            }
        )
        response_title = Title(
            provider="filmo.to",
            title_id=unsupported["title_id"],
            identity_anchor=unsupported["title_anchor"],
            slug=unsupported["slug"],
            display_title=unsupported["display_title"],
            search_key=identity.search_key(unsupported["display_title"]),
            media_type="movie",
            year=unsupported["year"],
            path=unsupported["path"],
            observed_at=unsupported["observed_at"],
            detail_status="complete",
        )
        response = Response(
            query_digest=request_digest(request),
            source_id="variants",
            provider="filmo.to",
            revision=1,
            snapshot_digest=unsupported["snapshot_digest"],
            listing_checked_at=NOW,
            total=1,
            offset=0,
            mapping="unresolved",
            rows=[response_row],
            titles=[response_title],
        )
        response.check_request(request, "variants")


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE release_data SET variant_anchor=NULL",
        "UPDATE release_data SET metadata='{}'",
        "UPDATE release_data SET language='eng'",
        "UPDATE release_data SET release_id=printf('%064d',1)",
        "UPDATE release_data SET entity_key=999",
        "UPDATE release_data SET first_seen_at=observed_at+1",
    ],
)
def test_hostile_variant_artifacts_fail_admission(tmp_path, statement):
    path, payload = catalog(tmp_path)
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA ignore_check_constraints=ON")
        db.execute(statement + " WHERE release_key=1")
    with pytest.raises((ContractError, sqlite3.IntegrityError)):
        schema.validate(path, payload)


@pytest.mark.parametrize(
    "mutation",
    [
        {"player_url": "https://example.invalid/player"},
        {"audio_languages": []},
        {"audio_languages": ["deu", "deu"]},
        {"subtitle_mode": "none", "subtitle_languages": ["deu"]},
        {"native_id": "0"},
        {"host": "https://example.invalid"},
        {"quality": {"labels": [], "source": "webdl", "resolution": True}},
    ],
)
def test_metadata_rejects_unsafe_or_contradictory_values(mutation):
    with pytest.raises(ContractError):
        release_metadata.validate({**offer(), **mutation})


def test_unknown_subtitles_do_not_become_absent_and_web_stays_generic():
    item = offer()
    item["quality"] = {"labels": ["WEB"], "source": "web", "resolution": None}
    checked = release_metadata.decode(dumps(item).decode())
    assert checked["subtitle_languages"] is None
    assert checked["quality"] == item["quality"]
    assert release_metadata.language(checked) == "deu"
    dual = copy.deepcopy(checked)
    dual["audio_languages"] = ["eng", "deu"]
    assert release_metadata.language(dual) == "mul"


def test_filmo_wire_supports_all_languages_without_widening_legacy_requests():
    request = Request(
        operation="recent",
        limit=100,
        params={"t": "search"},
        provider="filmo.to",
        languages=[],
    )
    assert request.languages == []
    assert "offer_hosts" not in request.wire()
    assert Request(
        operation="recent",
        limit=100,
        params={"t": "search"},
        provider="filmo.to",
        languages=["jpn", "ita", "spa"],
    ).languages == ["jpn", "ita", "spa"]
    with pytest.raises(ValueError):
        Request(
            operation="recent",
            limit=100,
            params={"t": "search"},
            provider="aniworld.to",
            languages=["jpn"],
        )
    with pytest.raises(ValueError):
        Request(
            operation="recent",
            params={"t": "movie"},
            provider="aniworld.to",
            offer_hosts=["VOE"],
        )
