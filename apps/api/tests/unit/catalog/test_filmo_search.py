import xml.etree.ElementTree as ET

import pytest
from catalog_core import identity, query
from catalog_core.protocol import Response, Row, Title
from catalog_core.providers.filmo import offer_metadata

from app.catalog.query_local import LocalRead, materialize
from app.catalog.search import rss


@pytest.mark.parametrize(
    "labels,expected_quality",
    [
        (["BluRay", "720p"], ".BluRay.720p"),
        (["WEB-DL", "1080p"], ".WEB-DL.1080p"),
        (["WEBRip", "720p"], ".WEBRip.720p"),
        (["WEB", "720p"], ""),
        (["720p"], ""),
        (["BluRay"], ""),
        (["WEB", "BluRay", "720p"], ""),
    ],
)
def test_filmo_rss_separates_audio_subtitles_and_uncertain_quality(
    labels, expected_quality
):
    metadata = offer_metadata("42", "VOE", "English Dub German Sub", labels)
    entity_id = identity.entity_id("filmo.to", "/movies/example/release/42")
    row = {
        "provider": "filmo.to",
        "title_id": identity.title_id("filmo.to", "/movies/example"),
        "entity_id": entity_id,
        "release_id": identity.variant_release_id(
            "filmo.to", entity_id, metadata["variant_anchor"]
        ),
        "snapshot_digest": "a" * 64,
        "title_anchor": "/movies/example",
        "entity_anchor": "/movies/example/release/42",
        "path": "/movies/example",
        "slug": "example",
        "display_title": "Example",
        "year": 2020,
        "kind": "movie",
        "language": "eng",
        "variant_anchor": metadata["variant_anchor"],
        "release_metadata": metadata,
        "native_season": None,
        "native_episode": None,
        "namespace": None,
        "external_id": None,
        "season": None,
        "episode": None,
        "first_seen_at": 1,
        "observed_at": 2,
        "mode": "download",
        "category": 2000,
        "canonical": None,
    }

    body = rss([row], 1, 0, seeders=1, leechers=0)
    root = ET.fromstring(body)
    item = root.find("./channel/item")
    assert item is not None
    title = item.findtext("title") or ""
    description = item.findtext("description") or ""
    attrs = [node.attrib for node in item if node.tag.endswith("attr")]
    language_attrs = [attr["value"] for attr in attrs if attr["name"] == "language"]
    assert "English" in title
    assert title == "Example.2020.English" + expected_quality + "-FILMO"
    assert "German" not in title
    assert language_attrs == ["English"]
    assert "German" in description
    assert all(label in description for label in labels)
    assert {attr["name"]: attr["value"] for attr in attrs}[
        "anibridge_subtitle_languages"
    ] == "deu"
    assert {attr["name"]: attr["value"] for attr in attrs}[
        "anibridge_audio_languages"
    ] == "eng"


def test_filmo_rss_rejects_incomplete_variant_rows_instead_of_dropping_results():
    with pytest.raises(ValueError, match="filmo_variant_metadata_required"):
        rss(
            [
                {
                    "provider": "filmo.to",
                    "title_id": "a" * 64,
                    "entity_id": "b" * 64,
                    "release_id": "c" * 64,
                    "title_anchor": "/movies/example",
                    "entity_anchor": "/movies/example/release",
                    "slug": "example",
                    "path": "/movies/example",
                    "kind": "movie",
                    "native_season": None,
                    "native_episode": None,
                    "language": "eng",
                    "mode": "download",
                    "variant_anchor": None,
                    "release_metadata": None,
                }
            ],
            1,
            0,
            seeders=0,
            leechers=0,
        )


def test_filmo_local_materialization_preserves_same_language_offers(tmp_path):
    title_anchor = "/movies/example"
    entity_anchor = "/movies/example/release"
    title_id = identity.title_id("filmo.to", title_anchor)
    entity_id = identity.entity_id("filmo.to", entity_anchor)
    snapshot = "d" * 64
    title = Title(
        provider="filmo.to",
        title_id=title_id,
        identity_anchor=title_anchor,
        slug="example",
        display_title="Example",
        search_key="example",
        media_type="movie",
        year=2020,
        path=title_anchor,
        observed_at=2,
        detail_status="complete",
    )
    rows = []
    for native_id, host, labels in (
        ("42", "VOE", ["BluRay", "720p"]),
        ("84", "Byse", ["WEB", "1080p"]),
    ):
        offer = offer_metadata(native_id, host, "English Dub German Sub", labels)
        rows.append(
            Row(
                provider="filmo.to",
                title_id=title_id,
                entity_id=entity_id,
                release_id=identity.variant_release_id(
                    "filmo.to", entity_id, offer["variant_anchor"]
                ),
                snapshot_digest=snapshot,
                title_anchor=title_anchor,
                entity_anchor=entity_anchor,
                path=title_anchor,
                slug="example",
                display_title="Example",
                year=2020,
                kind="movie",
                language="eng",
                variant_anchor=offer["variant_anchor"],
                release_metadata=offer,
                native_season=None,
                native_episode=None,
                namespace=None,
                external_id=None,
                season=None,
                episode=None,
                first_seen_at=1,
                observed_at=2,
            )
        )
    response = Response(
        query_digest="e" * 64,
        source_id="test-source",
        provider="filmo.to",
        revision=1,
        snapshot_digest=snapshot,
        listing_checked_at=2,
        total=len(rows),
        offset=0,
        mapping="unresolved",
        rows=rows,
        titles=[title],
    )
    database = tmp_path / "filmo-query.sqlite"
    local_metadata = materialize(database, [response])
    store = LocalRead(database, local_metadata, [])
    projected, total, _ = query.query(
        store, query.parse({"t": "movie", "q": "Example"}), now=3
    )
    assert total == 2 and len(projected) == 2
    assert {row["variant_anchor"] for row in projected} == {
        row.variant_anchor for row in rows
    }
    assert {row["release_metadata"]["host"] for row in projected} == {"VOE", "Byse"}
