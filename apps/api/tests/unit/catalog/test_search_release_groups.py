"""Provider suffixes in query RSS labels and stable grab identity."""

import xml.etree.ElementTree as ET

import pytest
from catalog_core import identity

from app.catalog.search import rss


def _episode_row(provider: str, mode: str = "download") -> dict:
    title_anchor = "/anime/stream/example"
    entity_anchor = title_anchor + "/staffel-1/episode-2"
    title_id = identity.title_id(provider, title_anchor)
    entity_id = identity.entity_id(provider, entity_anchor)
    return {
        "provider": provider,
        "title_id": title_id,
        "entity_id": entity_id,
        "release_id": identity.release_id(provider, entity_id, "de-dub"),
        "title_anchor": title_anchor,
        "entity_anchor": entity_anchor,
        "path": title_anchor,
        "slug": "example",
        "display_title": "Example",
        "year": 2020,
        "kind": "episode",
        "language": "de-dub",
        "variant_anchor": None,
        "release_metadata": None,
        "native_season": 1,
        "native_episode": 2,
        "namespace": None,
        "external_id": None,
        "season": None,
        "episode": None,
        "first_seen_at": 1,
        "observed_at": 2,
        "mode": mode,
        "category": 5070,
        "height": None,
        "estimated": False,
        "codec": None,
    }


@pytest.mark.parametrize(
    ("provider", "suffix"),
    [
        ("aniworld.to", "-ANIWORLD"),
        ("s.to", "-STO"),
        ("megakino", "-MEGAKINO"),
    ],
)
def test_query_rss_restores_provider_suffix(provider: str, suffix: str) -> None:
    row = _episode_row(provider)
    item = ET.fromstring(rss([row], 1, 0, seeders=1, leechers=0)).find("./channel/item")
    assert item is not None
    assert item.findtext("title") == f"Example.S01E02.German.Dub{suffix}"


def test_query_rss_suffix_precedes_strm_variant_without_changing_infohash() -> None:
    download = _episode_row("s.to")
    stream = _episode_row("s.to", mode="strm")
    items = ET.fromstring(rss([download, stream], 2, 0, seeders=1, leechers=0)).findall(
        "./channel/item"
    )
    titles = [item.findtext("title") for item in items]
    assert titles == [
        "Example.S01E02.German.Dub-STO",
        "Example.S01E02.German.Dub-STO.STRM",
    ]

    infohashes = [
        next(
            attr.attrib["value"]
            for attr in item
            if attr.tag.endswith("attr") and attr.attrib.get("name") == "infohash"
        )
        for item in items
    ]
    assert infohashes == [
        identity.infohash(download["release_id"], "download"),
        identity.infohash(stream["release_id"], "strm"),
    ]
