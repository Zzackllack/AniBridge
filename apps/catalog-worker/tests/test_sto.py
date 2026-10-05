"""Generated Serienstream structures; separate from any live-provider proof."""

import pytest
from catalog_core import identity
from catalog_worker import sto
from catalog_worker.state import State

TITLE = "/serie/example"
EPISODE = TITLE + "/staffel-0/episode-1"
NOW = 1800000000


def html(body):
    return ("<html><body>" + body + "</body></html>").encode()


def test_language_labels_and_canonical_inputs_are_provider_specific():
    page = sto.parse(
        html("""<h1>Example</h1><h2>S00E01: Anfang (Beginning)</h2>
        <a href="/jahr/2020">2020</a>
        <a href="https://www.imdb.com/title/tt1234567/">IMDb</a>
        <button data-play-url="/r/private" data-provider-name="VOE" data-language-label="Englisch" data-language-id="2"></button>
        <button data-play-url="/r/private" data-provider-name="VOE" data-language-label="Deutsch"></button>
        <button data-play-url="/r/private" data-provider-name="VOE" data-language-label="Unknown"></button>"""),
        "detail",
        EPISODE,
    )
    assert page.languages == ("de-dub", "en-dub")
    assert page.unknown_languages == 1
    assert page.episode_title == "Beginning"
    assert page.year == 2020 and page.explicit_imdb == "tt1234567"
    assert "private" not in repr(page)
    assert sto.coordinates(EPISODE) == (0, 1)
    with pytest.raises(ValueError):
        sto.parse(html("<h1>Example</h1>"), "detail", EPISODE)


def test_listing_paging_rejects_ambiguous_or_partial_traversal():
    page = sto.parse(
        html(
            f'<a href="{TITLE}">Example</a><a rel="next" href="/serien?by=alpha&amp;page=2">Next</a>'
        ),
        "listing",
    )
    assert page.links[0].path == TITLE
    assert page.next_pages == ("/serien?by=alpha&page=2",)
    for target in (
        "/serien?page=2",
        "/serien?by=alpha&page=2&page=3",
        "https://other.invalid/serien?by=alpha",
        "/serien?by=alpha&search=query",
    ):
        with pytest.raises(ValueError):
            sto.parse(
                html(
                    f'<a href="{TITLE}">Example</a><a rel="next" href="{target}">Next</a>'
                ),
                "listing",
            )
    with pytest.raises(ValueError):
        sto.parse(b'<html><body><a href="/serie/example">Example</a>', "listing")


def test_unrelated_navigation_and_help_headings_preserve_episode_metadata():
    page = sto.parse(
        html('''<nav><a href="/serienkalender">Calendar</a>
        <a href="/serienwuensche">Requests</a></nav>
        <h1>Example</h1><h2>S00E01: Anfang (Beginning)</h2>
        <button data-play-url="/r/private" data-provider-name="VOE"
                data-language-label="Deutsch"></button>
        <h2>Comments</h2><h2>Frequently asked questions</h2>'''),
        "detail",
        EPISODE,
    )
    assert page.episode_title == "Beginning"
    assert page.languages == ("de-dub",)
    assert page.next_pages == ()
    with pytest.raises(ValueError, match="conflicting episode titles"):
        sto.parse(
            html('''<h1>Example</h1><h2>S00E01: Anfang (Beginning)</h2>
            <h2>S00E01: Andere (Different)</h2>'''),
            "detail",
            EPISODE,
        )


def test_native_identity_and_first_seen_survive_restart(tmp_path):
    filename = tmp_path / "sto.sqlite"
    state = State(filename, "s.to")
    state.listing(sto.parse(html(f'<a href="{TITLE}">Example</a>'), "listing"), NOW)
    state.detail(
        state.claim(NOW),
        sto.parse(
            html(f'<h1>Example</h1><a href="{TITLE}/staffel-0">Specials</a>'),
            "detail",
            TITLE,
        ),
        NOW,
    )
    state.detail(
        state.claim(NOW),
        sto.parse(
            html(f'<a href="{EPISODE}">Beginning</a>'), "detail", TITLE + "/staffel-0"
        ),
        NOW,
    )
    work = state.claim(NOW)
    page = sto.parse(
        html(
            '<h1>Example</h1><button data-play-url="/r/private" data-provider-name="VOE" data-language-label="Englisch"></button>'
        ),
        "detail",
        EPISODE,
    )
    state.detail(work, page, NOW)
    state.close()
    state = State(filename, "s.to")
    state.detail(work, page, NOW + 60)
    record = dict(state.db.execute("SELECT * FROM release").fetchone())
    assert record["release_id"] == identity.release_id(
        "s.to", identity.entity_id("s.to", EPISODE), "en-dub"
    )
    assert record["first_seen_at"] == NOW and record["observed_at"] == NOW + 60
    assert state.db.execute("SELECT count(*) FROM canonical_episode").fetchone()[0] == 0
    state.close()


