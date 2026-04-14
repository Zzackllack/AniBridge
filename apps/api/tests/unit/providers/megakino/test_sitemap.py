from datetime import datetime
import warnings

import pytest

from app.providers.megakino.client import MegakinoClient, slug_to_title
from app.providers.megakino.sitemap import (
    MegakinoIndex,
    MegakinoIndexEntry,
    parse_sitemap_xml,
)


SAMPLE_XML = """
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://megakino1.to/serials/5881-i-love-la-1-staffel.html</loc>
    <lastmod>2025-12-17</lastmod>
  </url>
  <url>
    <loc>https://megakino1.to/films/5920-die-my-love.html</loc>
    <lastmod>2025-12-17</lastmod>
  </url>
</urlset>
"""


def test_parse_sitemap_xml_extracts_entries():
    """Ensure sitemap parsing extracts film and serial slugs."""
    entries = parse_sitemap_xml(SAMPLE_XML)
    assert len(entries) == 2
    slugs = {entry.slug for entry in entries}
    assert "i-love-la-1-staffel" in slugs
    assert "die-my-love" in slugs
    kinds = {entry.kind for entry in entries}
    assert "serial" in kinds
    assert "film" in kinds


def test_slug_to_title_humanizes():
    """Ensure slug-to-title conversion humanizes hyphenated slugs."""
    assert slug_to_title("avengers-endgame") == "Avengers Endgame"


def test_megakino_client_search_matches_tokens():
    """Ensure token matching returns the best Megakino sitemap result."""
    client = MegakinoClient(sitemap_url="http://example.com", refresh_hours=0.0)
    client._index = MegakinoIndex(
        entries={
            "avengers-endgame": MegakinoIndexEntry(
                slug="avengers-endgame",
                url="https://megakino1.to/films/125-avengers-endgame.html",
                kind="film",
                lastmod=datetime(2025, 12, 17),
            ),
            "percy-jackson-die-serie-2-staffel": MegakinoIndexEntry(
                slug="percy-jackson-die-serie-2-staffel",
                url="https://megakino1.to/serials/5919-percy-jackson-die-serie-2-staffel.html",
                kind="serial",
                lastmod=datetime(2025, 12, 17),
            ),
        },
        fetched_at=0.0,
    )

    results = client.search("Avengers Endgame 2019", limit=3)
    assert results
    assert results[0].slug == "avengers-endgame"


def test_megakino_resolve_direct_url_filters_speedfiles(monkeypatch):
    client = MegakinoClient(sitemap_url="http://example.com", refresh_hours=0.0)

    monkeypatch.setattr(client, "resolve_url", lambda slug: "https://megakino1.to/page")
    monkeypatch.setattr(
        "app.providers.megakino.client.get_megakino_base_url",
        lambda: "https://megakino1.to",
    )
    monkeypatch.setattr(
        "app.providers.megakino.client._warm_megakino_session",
        lambda base_url: None,
    )
    monkeypatch.setattr(
        "app.providers.megakino.client.http_get",
        lambda *args, **kwargs: type(
            "Response",
            (),
            {"text": "<html></html>", "raise_for_status": lambda self: None},
        )(),
    )
    monkeypatch.setattr(
        "app.providers.megakino.client._extract_host_links",
        lambda html: ["https://speedfiles.example/embed/123"],
    )

    with pytest.raises(ValueError, match="No video host iframes found"):
        client.resolve_direct_url("slug")


def test_megakino_resolve_direct_url_warns_for_preferred_provider_alias(monkeypatch):
    client = MegakinoClient(sitemap_url="http://example.com", refresh_hours=0.0)

    monkeypatch.setattr(client, "resolve_url", lambda slug: "https://megakino1.to/page")
    monkeypatch.setattr(
        "app.providers.megakino.client.get_megakino_base_url",
        lambda: "https://megakino1.to",
    )
    monkeypatch.setattr(
        "app.providers.megakino.client._warm_megakino_session",
        lambda base_url: None,
    )
    monkeypatch.setattr(
        "app.providers.megakino.client.http_get",
        lambda *args, **kwargs: type(
            "Response",
            (),
            {"text": "<html></html>", "raise_for_status": lambda self: None},
        )(),
    )
    monkeypatch.setattr(
        "app.providers.megakino.client._extract_host_links",
        lambda html: ["https://voe.sx/e/abc123"],
    )
    monkeypatch.setattr(
        "app.providers.megakino.client.resolve_host_url",
        lambda url: ("https://cdn.example/master.m3u8", "VOE"),
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        resolved = client.resolve_direct_url("slug", preferred_provider="VOE")

    assert resolved == ("https://cdn.example/master.m3u8", "VOE")
    assert any(item.category is DeprecationWarning for item in caught)


def test_megakino_resolve_direct_url_prefers_matching_host_domain(monkeypatch):
    client = MegakinoClient(sitemap_url="http://example.com", refresh_hours=0.0)

    monkeypatch.setattr(client, "resolve_url", lambda slug: "https://megakino1.to/page")
    monkeypatch.setattr(
        "app.providers.megakino.client.get_megakino_base_url",
        lambda: "https://megakino1.to",
    )
    monkeypatch.setattr(
        "app.providers.megakino.client._warm_megakino_session",
        lambda base_url: None,
    )
    monkeypatch.setattr(
        "app.providers.megakino.client.http_get",
        lambda *args, **kwargs: type(
            "Response",
            (),
            {"text": "<html></html>", "raise_for_status": lambda self: None},
        )(),
    )
    monkeypatch.setattr(
        "app.providers.megakino.client._extract_host_links",
        lambda html: [
            "https://streamtape.com/e/first",
            "https://voe.sx/e/second",
        ],
    )
    monkeypatch.setattr(
        "app.providers.megakino.client.resolve_host_url",
        lambda url: (None, "EMBED"),
    )

    resolved = client.resolve_direct_url("slug", preferred_host="https://voe.sx/embed")

    assert resolved == ("https://voe.sx/e/second", "EMBED")
