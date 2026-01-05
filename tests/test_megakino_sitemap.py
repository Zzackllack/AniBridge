from datetime import datetime

from app.providers.megakino.client import MegakinoClient, slug_to_title
from app.providers.megakino.sitemap import (
    MegakinoIndex,
    MegakinoIndexEntry,
    parse_sitemap_xml,
)


SAMPLE_XML = """
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://megakino.lol/serials/5881-i-love-la-1-staffel.html</loc>
    <lastmod>2025-12-17</lastmod>
  </url>
  <url>
    <loc>https://megakino.lol/films/5920-die-my-love.html</loc>
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
                url="https://megakino.lol/films/125-avengers-endgame.html",
                kind="film",
                lastmod=datetime(2025, 12, 17),
            ),
            "percy-jackson-die-serie-2-staffel": MegakinoIndexEntry(
                slug="percy-jackson-die-serie-2-staffel",
                url="https://megakino.lol/serials/5919-percy-jackson-die-serie-2-staffel.html",
                kind="serial",
                lastmod=datetime(2025, 12, 17),
            ),
        },
        fetched_at=0.0,
    )

    results = client.search("Avengers Endgame 2019", limit=3)
    assert results
    assert results[0].slug == "avengers-endgame"
