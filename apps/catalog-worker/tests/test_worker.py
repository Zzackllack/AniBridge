import sqlite3

import pytest
from catalog_core import artifact, identity, manifest, schema
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from catalog_worker.aniworld import Link, Page, parse
from catalog_worker.state import State

NOW = 1800000000
TITLE = "/anime/stream/example"
EPISODE = TITLE + "/staffel-1/episode-2"


def seed(path):
    state = State(path, "aniworld.to")
    assert state.listing(Page((Link(TITLE, "Example"),), (), 0, None), NOW)
    state.detail(
        state.claim(NOW), Page((Link(EPISODE, "Second"),), (), 0, "Example"), NOW
    )
    state.detail(state.claim(NOW), Page((), ("de-dub",), 0, "Second"), NOW)
    return state


def test_parser_positive_languages_and_structure():
    page = parse(
        b'<html><body><h1>Example</h1><li data-lang-key="1" data-link-target="/redirect/private"></li><li data-lang-key="2" data-link-target="/redirect/private2"></li><li data-lang-key="3" data-link-target="/redirect/private3"></li><li data-lang-key="99" data-link-target="/redirect/private4"></li></body></html>',
        "detail",
    )
    assert page.languages == ("de-dub", "de-sub", "en-sub")
    assert page.unknown_languages == 1
    assert "private" not in repr(page)
    for body in (b"<html>empty</html>", b"<html>cf-turnstile captcha-form</html>"):
        with pytest.raises(ValueError):
            parse(body, "listing")


def test_restart_preserves_discovery_and_due_work(tmp_path):
    filename = tmp_path / "worker.sqlite"
    state = seed(filename)
    row = tuple(state.db.execute("SELECT * FROM release").fetchone())
    work = dict(state.db.execute("SELECT * FROM work WHERE kind='episode'").fetchone())
    state.close()
    state = State(filename, "aniworld.to")
    state.detail(work, Page((), ("de-dub", "en-sub"), 0, "Edited title"), NOW + 20000)
    old = state.db.execute("SELECT * FROM release WHERE language='de-dub'").fetchone()
    new = state.db.execute("SELECT * FROM release WHERE language='en-sub'").fetchone()
    assert old["first_seen_at"] == row[3] == NOW
    assert new["first_seen_at"] == NOW + 20000
    checked = state.db.execute(
        "SELECT checked_at FROM work WHERE path=?", (EPISODE,)
    ).fetchone()[0]
    state.listing(Page((Link(TITLE, "Renamed label"),), (), 0, None), NOW + 20001)
    assert (
        state.db.execute(
            "SELECT checked_at FROM work WHERE path=?", (EPISODE,)
        ).fetchone()[0]
        == checked
    )
    state.close()


def test_count_collapse_and_challenge_keep_good_rows(tmp_path):
    state = seed(tmp_path / "worker.sqlite")
    assert not state.listing(Page((), (), 0, None), NOW + 14400)
    assert state.db.execute("SELECT count(*) FROM release").fetchone()[0] == 1
    state.failure(None, "challenge_or_block", NOW + 15000)
    assert state.meta()["blocked_until"] == NOW + 15000 + 900
    assert state.db.execute("SELECT first_seen_at FROM release").fetchone()[0] == NOW
    with pytest.raises(ValueError, match="clock_error"):
        state.clock(NOW - 1000) if state.clock(NOW) else None
    state.close()


def test_leases_request_caps_and_expired_claim(tmp_path):
    state = State(tmp_path / "worker.sqlite", "aniworld.to")
    state.listing(Page((Link(TITLE, "Example"),), (), 0, None), NOW)
    first = state.claim(NOW)
    assert first and not state.claim(NOW + 119)
    assert state.claim(NOW + 120)["path"] == first["path"]
    assert state.allow_request(NOW, 2, 2)
    assert not state.allow_request(NOW + 1, 2, 2)
    assert state.allow_request(NOW + 2, 2, 2)
    assert not state.allow_request(NOW + 20, 2, 2)
    assert state.allow_request(NOW + 3600, 2, 2)
    state.close()






def test_rejected_language_collapse_does_not_refresh_observation(tmp_path):
    state = seed(tmp_path / "worker.sqlite")
    work = dict(state.db.execute("SELECT * FROM work WHERE kind='episode'").fetchone())
    before = tuple(state.db.execute("SELECT * FROM entity").fetchone())
    state.detail(work, Page((), (), 0, "Wrong replacement"), NOW + 100)
    assert tuple(state.db.execute("SELECT * FROM entity").fetchone()) == before
    assert state.db.execute("SELECT observed_at FROM release").fetchone()[0] == NOW
    state.close()


def test_unknown_language_gap_survives_other_page_success(tmp_path):
    state = seed(tmp_path / "worker.sqlite")
    episode = dict(
        state.db.execute("SELECT * FROM work WHERE kind='episode'").fetchone()
    )
    title = dict(state.db.execute("SELECT * FROM work WHERE kind='title'").fetchone())
    state.detail(episode, Page((), ("de-dub",), 1, "Second"), NOW + 1)
    state.detail(title, Page((Link(EPISODE, "Second"),), (), 0, "Example"), NOW + 2)
    assert (
        state.db.execute("SELECT detail_status FROM title").fetchone()[0] == "partial"
    )
    state.detail(episode, Page((), ("de-dub",), 0, "Second"), NOW + 3)
    assert (
        state.db.execute("SELECT detail_status FROM title").fetchone()[0] == "complete"
    )
    state.close()


def test_historical_cadence_and_new_language_reactivation(tmp_path):
    state = seed(tmp_path / "worker.sqlite")
    work = dict(state.db.execute("SELECT * FROM work WHERE kind='episode'").fetchone())
    later = NOW + 31 * 86400
    state.detail(work, Page((), ("de-dub",), 0, "Second"), later)
    assert (
        state.db.execute("SELECT due FROM work WHERE path=?", (EPISODE,)).fetchone()[0]
        == later + 604800
    )
    state.detail(work, Page((), ("de-dub", "en-sub"), 0, "Second"), later + 1)
    assert (
        state.db.execute("SELECT due FROM work WHERE path=?", (EPISODE,)).fetchone()[0]
        == later + 1 + 14400
    )
    state.close()


def test_paginated_listing_restart_and_atomic_acceptance(tmp_path):
    from catalog_worker.listing import Links, Traversal

    filename = tmp_path / "worker.sqlite"
    state = State(filename, "aniworld.to")
    traversal = Traversal(state.db)
    assert traversal.next_path("/animes-alphabet") == "/animes-alphabet"
    assert not traversal.add(
        "/animes-alphabet",
        Page((Link(TITLE, "Example"),), (), 0, None, ("/animes-alphabet/2",)),
    )
    assert state.db.execute("SELECT count(*) FROM title").fetchone()[0] == 0
    state.close()
    state = State(filename, "aniworld.to")
    traversal = Traversal(state.db)
    assert traversal.next_path("/animes-alphabet") == "/animes-alphabet/2"
    assert traversal.add(
        "/animes-alphabet/2", Page((Link(TITLE + "-two", "Two"),), (), 0, None)
    )
    # A crash after the final page but before acceptance is resumable too.
    state.close()
    state = State(filename, "aniworld.to")
    traversal = Traversal(state.db)
    assert traversal.next_path("/animes-alphabet") is None
    state.listing(Page(Links(state.db), (), 0, None), NOW, accepted=traversal.clear)
    assert state.db.execute("SELECT count(*) FROM title").fetchone()[0] == 2
    assert state.db.execute("SELECT count(*) FROM listing_page").fetchone()[0] == 0
    state.close()


def test_pagination_cycle_does_not_admit_partial_listing(tmp_path):
    from catalog_worker.listing import Traversal

    state = State(tmp_path / "worker.sqlite", "aniworld.to")
    traversal = Traversal(state.db)
    traversal.next_path("/animes-alphabet")
    with pytest.raises(ValueError, match="cycle"):
        traversal.add(
            "/animes-alphabet",
            Page((Link(TITLE, "Example"),), (), 0, None, ("/animes-alphabet",)),
        )
    assert state.meta()["listing_checked_at"] == 0
    assert state.db.execute("SELECT count(*) FROM title").fetchone()[0] == 0
    state.close()




def test_absence_needs_own_three_complete_observations_over_48h(tmp_path):
    state = seed(tmp_path / "worker.sqlite")
    rid = state.db.execute("SELECT release_id FROM release").fetchone()[0]
    with state.db:
        for moment in (NOW, NOW + 1, NOW + 2):
            state._observe_absence("release", [rid], set(), moment)
        # A different entity checked two days later does not stretch this
        # record's three clustered observations into a valid 48-hour span.
        state._observe_absence("release", [], set(), NOW + 172800)
        assert (
            state.db.execute(
                "SELECT tombstoned FROM omissions WHERE id=?", (rid,)
            ).fetchone()[0]
            == 0
        )
        state._observe_absence("release", [rid], set(), NOW + 172800)
        assert (
            state.db.execute(
                "SELECT tombstoned FROM omissions WHERE id=?", (rid,)
            ).fetchone()[0]
            == 1
        )
        state._observe_absence("release", [rid], {rid}, NOW + 172801)
        assert (
            state.db.execute("SELECT 1 FROM omissions WHERE id=?", (rid,)).fetchone()
            is None
        )
        assert (
            state.db.execute("SELECT first_seen_at FROM release").fetchone()[0] == NOW
        )
    state.close()




def test_complete_empty_episode_and_truncation_are_distinct():
    body = (
        b'<html><body><h1>Example</h1><div class="hosterSiteVideo"></div></body></html>'
    )
    page = parse(body, "detail", EPISODE)
    assert page.languages == () and page.unknown_languages == 0
    for truncated in (body[:-7], body[:-14], body[:30]):
        with pytest.raises(ValueError, match="incomplete HTML"):
            parse(truncated, "detail", EPISODE)
    with pytest.raises(ValueError, match="unexpected episode"):
        parse(
            b'<html><body><h1>Example</h1><a href="/anime/stream/other/staffel-1">Other</a></body></html>',
            "detail",
            EPISODE,
        )


def test_unrecognized_pagination_does_not_count_as_complete_listing():
    for href in ("/animes-alphabet?page=2", "/animes-alphabet/2"):
        body = f'<html><body><a href="{TITLE}">Example</a><a href="{href}">2</a></body></html>'.encode()
        with pytest.raises(ValueError, match="pagination"):
            parse(body, "listing", "/animes-alphabet")
    # An entirely unrelated title cannot complete this title's detail work.
    with pytest.raises(ValueError, match="title/season"):
        parse(
            b'<html><body><a href="/anime/stream/other/staffel-1">Other</a></body></html>',
            "detail",
            TITLE,
        )


def test_inflight_positive_pages_preserve_provider_block_and_last_good(tmp_path):
    state = seed(tmp_path / "worker.sqlite")
    try:
        work = dict(
            state.db.execute("SELECT * FROM work WHERE kind='episode'").fetchone()
        )
        state.failure(work, "challenge_or_block", NOW + 1)
        blocked = state.meta()["blocked_until"]
        # Another already-in-flight response can safely add facts, but cannot
        # clear the provider-wide challenge observed by its concurrent sibling.
        state.detail(work, Page((), ("de-dub", "en-sub"), 0, "Second"), NOW + 2)
        assert state.meta()["state"] == "blocked"
        assert state.meta()["blocked_until"] == blocked
        assert (
            state.db.execute(
                "SELECT first_seen_at FROM release WHERE language='de-dub'"
            ).fetchone()[0]
            == NOW
        )
        state.listing(Page((Link(TITLE, "Example"),), (), 0, None), NOW + 3)
        assert state.meta()["state"] == "blocked"
        state.detail(work, Page((), ("de-dub", "en-sub"), 0, "Second"), blocked + 1)
        assert state.meta()["state"] == "partial"
    finally:
        state.close()
