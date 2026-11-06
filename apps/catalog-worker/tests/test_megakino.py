"""Generated sitemap/player labels; no live-site structure or media proof."""

import json
from xml.etree.ElementTree import ParseError

import pytest
from catalog_core import identity
from catalog_worker import megakino
from catalog_worker.listing import Links, Traversal
from catalog_worker.state import State
from defusedxml.common import DefusedXmlException

ORIGIN = "https://movies.invalid"
PATH = "/films/123-example.html"
NOW = 1800000000
NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def sitemap(paths, index=False):
    root, entry = ("sitemapindex", "sitemap") if index else ("urlset", "url")
    return (
        f'<{root} xmlns="{NS}">'
        + "".join(f"<{entry}><loc>{ORIGIN}{path}</loc></{entry}>" for path in paths)
        + f"</{root}>"
    ).encode()


def detail(label=None):
    attribute = f' data-language-label="{label}"' if label else ""
    movie = {
        "@type": "Movie",
        "url": ORIGIN + PATH,
        "datePublished": "2020-03-01",
        "inLanguage": "de",
        "alternateName": ["Original Example"],
        "sameAs": "https://www.imdb.com/title/tt1234567/",
    }
    return (
        f'<html><body><h1>Observed Example</h1><script type="application/ld+json">{json.dumps(movie)}</script><iframe src="https://host.invalid/private"{attribute}></iframe></body></html>'
    ).encode()


def test_sitemap_traversal_restarts_without_publishing_partial_listing(tmp_path):
    filename = tmp_path / "worker.sqlite"
    state = State(filename, "megakino")
    traversal = Traversal(state.db)
    assert traversal.next_path("/sitemap.xml") == "/sitemap.xml"
    assert not traversal.add(
        "/sitemap.xml",
        megakino.parse(
            sitemap(["/sitemap1.xml", "/sitemap2.xml"], True), "listing", origin=ORIGIN
        ),
    )
    assert not traversal.add(
        "/sitemap1.xml", megakino.parse(sitemap([PATH]), "listing", origin=ORIGIN)
    )
    assert state.meta()["listing_checked_at"] == 0
    state.close()
    state = State(filename, "megakino")
    traversal = Traversal(state.db)
    assert traversal.next_path("/sitemap.xml") == "/sitemap2.xml"
    assert traversal.add(
        "/sitemap2.xml",
        megakino.parse(
            sitemap(["/serials/124-example-series.html"]), "listing", origin=ORIGIN
        ),
    )
    state.listing(
        megakino.Page(Links(state.db), (), 0, None), NOW, accepted=traversal.clear
    )
    assert {
        tuple(r) for r in state.db.execute("SELECT media_type,detail_status FROM title")
    } == {("movie", "pending"), ("unknown", "pending")}
    assert state.db.execute("SELECT count(*) FROM canonical_title").fetchone()[0] == 0
    state.close()


@pytest.mark.parametrize(
    "body",
    [
        b'<!DOCTYPE urlset [<!ENTITY x SYSTEM "file:///etc/passwd">]><urlset>&x;</urlset>',
        b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url>',
        sitemap([PATH]).replace(ORIGIN.encode(), b"https://foreign.invalid"),
        sitemap(["/sitemap.xml?query=secret"], True),
        sitemap(["/file.xml"], True),
    ],
)
def test_bad_sitemap_cannot_admit_external_paths_or_partial_absence(body):
    with pytest.raises((ValueError, ParseError, DefusedXmlException)):
        megakino.parse(body, "listing", origin=ORIGIN)


def test_unlabelled_player_and_original_language_never_invent_release(tmp_path):
    page = megakino.parse(detail(), "detail", PATH, origin=ORIGIN)
    assert page.languages == () and page.unknown_languages == 1
    assert page.title == "Observed Example" and page.year == 2020
    assert page.explicit_imdb == "tt1234567"
    assert "private" not in repr(page) and "host.invalid" not in repr(page)
    state = State(tmp_path / "worker.sqlite", "megakino")
    state.listing(megakino.parse(sitemap([PATH]), "listing", origin=ORIGIN), NOW)
    state.detail(state.claim(NOW), page, NOW)
    title = dict(state.db.execute("SELECT * FROM title").fetchone())
    entity = dict(state.db.execute("SELECT * FROM entity").fetchone())
    assert (
        title["display_title"] == "Observed Example"
        and title["detail_status"] == "partial"
    )
    assert (
        entity["kind"] == "movie"
        and entity["native_season"] is None
        and entity["native_episode"] is None
    )
    assert state.db.execute("SELECT count(*) FROM release").fetchone()[0] == 0
    state.close()


def test_small_script_stub_or_foreign_movie_never_marks_detail_complete():
    with pytest.raises(ValueError):
        megakino.parse(
            b'<meta charset="utf-8"><script>location.reload()</script>',
            "detail",
            PATH,
            origin=ORIGIN,
        )
    with pytest.raises(ValueError):
        megakino.parse(
            detail("Deutsch").replace(PATH.encode(), b"/films/999-another.html"),
            "detail",
            PATH,
            origin=ORIGIN,
        )


def test_sitemap_origin_alias_is_explicit_and_path_only():
    foreign = sitemap([PATH]).replace(ORIGIN.encode(), b"https://megakino3.com")
    with pytest.raises(ValueError, match="foreign sitemap target"):
        megakino.parse(foreign, "listing", origin=ORIGIN)
    page = megakino.parse(
        foreign, "listing", origin=ORIGIN, sitemap_origins=("https://megakino3.com",)
    )
    assert page.links[0].path == PATH
    assert "megakino3" not in repr(page)
