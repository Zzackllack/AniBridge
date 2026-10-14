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
        html("""<nav><a href="/serienkalender">Calendar</a>
        <a href="/serienwuensche">Requests</a></nav>
        <h1>Example</h1><h2>S00E01: Anfang (Beginning)</h2>
        <button data-play-url="/r/private" data-provider-name="VOE"
                data-language-label="Deutsch"></button>
        <h2>Comments</h2><h2>Frequently asked questions</h2>"""),
        "detail",
        EPISODE,
    )
    assert page.episode_title == "Beginning"
    assert page.languages == ("de-dub",)
    assert page.next_pages == ()
    with pytest.raises(ValueError, match="conflicting episode titles"):
        sto.parse(
            html("""<h1>Example</h1><h2>S00E01: Anfang (Beginning)</h2>
            <h2>S00E01: Andere (Different)</h2>"""),
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


def test_current_header_year_range_and_genre_navigation():
    page = sto.parse(
        b'<html><body><h1>Breaking Bad</h1><p class="small text-muted mb-2"><a href="/jahr/2008">2008</a> - <a href="/jahr/2013">2013</a></p><a href="/serien?by=genre">Genres</a><a href="/serie/breaking-bad/staffel-1">Season 1</a></body></html>',
        "detail",
        "/serie/breaking-bad",
    )
    assert page.year == 2008 and len(page.links) == 1


def test_observed_subtitle_labels_and_unavailable_metadata(tmp_path):
    page = sto.parse(
        html(
            '<h1>Example</h1><h2>S00E01: (Beginning)</h2><button data-play-url="/discarded" data-provider-name="VOE" data-language-label="Ger-Sub"></button>'
        ),
        "detail",
        EPISODE,
    )
    assert page.languages == ("de-sub",) and page.unknown_languages == 0
    assert page.episode_title == "Beginning" and page.episode_aliases == ()
    state = State(tmp_path / "state.sqlite", "s.to")
    from catalog_worker.aniworld import Link

    tid = state.discover(Link(TITLE, "Example"), NOW)
    state.db.execute(
        "INSERT INTO work(path,title_id,kind,due) VALUES(?,?,?,?)",
        (EPISODE, tid, "episode", NOW),
    )
    state.db.commit()
    work = dict(
        state.db.execute("SELECT * FROM work WHERE path=?", (EPISODE,)).fetchone()
    )
    state.detail(work, page, NOW)
    previous = dict(state.db.execute("SELECT * FROM release").fetchone())
    with state.db:
        state.db.execute("UPDATE work SET failures=7 WHERE path=?", (EPISODE,))
    unavailable = sto.parse(
        html(
            '<h1>Example</h1><h2>S00E01: (Beginning)</h2><div class="player-wrap"><p>😰 Kein Videoplayer für diese Episode verfügbar.</p></div>'
        ),
        "detail",
        EPISODE,
    )
    assert (
        unavailable.availability == "unavailable"
        and unavailable.episode_title == "Beginning"
    )
    for age in (1, 86401, 172801, 259201):
        state.detail(work, unavailable, NOW + age)
    assert dict(state.db.execute("SELECT * FROM release").fetchone()) == previous
    assert (
        state.db.execute(
            "SELECT failures FROM work WHERE path=?", (EPISODE,)
        ).fetchone()[0]
        == 7
    )
    assert (
        state.db.execute(
            "SELECT count(*) FROM omissions WHERE kind='release'"
        ).fetchone()[0]
        == 0
    )
    assert state.db.execute("SELECT count(*) FROM quarantine").fetchone()[0] == 0
    from catalog_worker.progress import measure

    assert (
        measure(state.db, state.meta(), NOW + 259201)[
            "unavailable_episode_observations"
        ]
        == 1
    )
    assert not measure(state.db, state.meta(), NOW + 259201)["detail_evidence_complete"]
    state.close()


@pytest.mark.parametrize(
    "body,reason",
    [
        ("<h1>Example</h1><h2>S00E01: (Beginning)</h2>", "structure_changed"),
        (
            '<h1>Example</h1><h2>S00E01: (Beginning)</h2><div class="player-wrap"></div>',
            "video_section_missing",
        ),
        ('<h1>Example</h1><form id="challenge-form"></form>', "access_interstitial"),
    ],
)
def test_missing_video_reason_is_explicit(body, reason):
    with pytest.raises(ValueError, match=reason):
        sto.parse(html(body), "detail", EPISODE)


def test_unavailable_without_heading_preserves_name_releases_and_retry_history(
    tmp_path,
):
    from catalog_worker.aniworld import Link

    state = State(tmp_path / "state.sqlite", "s.to")
    tid = state.discover(Link(TITLE, "Example"), NOW)
    with state.db:
        state.db.execute(
            "INSERT INTO work(path,title_id,kind,due) VALUES(?,?,'episode',?)",
            (EPISODE, tid, NOW),
        )
    work = dict(
        state.db.execute("SELECT * FROM work WHERE path=?", (EPISODE,)).fetchone()
    )
    state.detail(
        work,
        sto.parse(
            html(
                '<h1>Example</h1><h2>S00E01: (A useful name)</h2><button data-play-url="/discarded" data-provider-name="VOE" data-language-label="Ger-Sub"></button>'
            ),
            "detail",
            EPISODE,
        ),
        NOW,
    )
    previous = dict(state.db.execute("SELECT * FROM release").fetchone())
    page = sto.parse(
        html(
            '<h1>Example</h1><div class="player-wrap"><p>Kein Videoplayer für diese Episode verfügbar.</p></div>'
        ),
        "detail",
        EPISODE,
    )
    assert (
        page.availability == "unavailable"
        and page.episode_title is None
        and page.languages == ()
    )
    state.detail(work, page, NOW + 1)
    assert (
        state.db.execute("SELECT display_title FROM entity").fetchone()[0]
        == "A useful name"
    )
    assert dict(state.db.execute("SELECT * FROM release").fetchone()) == previous
    assert not state.db.execute("SELECT 1 FROM omissions").fetchone()
    state.close()


def test_season_navigation_without_episode_rows_is_explicit_gap():
    from catalog_core.diagnostics import reason

    body = html(
        f'<h1>Example</h1><a href="{TITLE}/staffel-1">Season 1</a><a href="{TITLE}/staffel-2">Season 2</a>'
    )
    with pytest.raises(ValueError) as caught:
        sto.parse(body, "detail", TITLE + "/staffel-2")
    assert reason(caught.value) == "parent_children_missing"
