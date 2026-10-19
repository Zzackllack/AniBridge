"""Automatic correspondence needs independent unique episode names."""

from catalog_core.identity import mapping_id, title_id
from catalog_worker.aniworld import Link, Page
from catalog_worker.canonical_cache import apply, store
from catalog_worker.mapping import CanonicalEpisode
from catalog_worker.state import State


def test_unique_names_prove_season_and_annotation_without_number_guess(tmp_path):
    state = State(tmp_path / "state.sqlite", "aniworld.to")
    title = "/anime/stream/example"
    tid = title_id(state.provider, title)
    mid = mapping_id(state.provider, tid, "tvdb", "123")
    names = [
        "First unique story",
        "Another distinct story",
        "The ending [Final Episode]",
    ]
    state.listing(Page((Link(title, "Example"),), (), 0, None), 1800000000)
    paths = [title + f"/staffel-8/episode-{n}" for n in range(1, 4)]
    state.detail(
        state.claim(1800000000),
        Page(tuple(Link(p, n) for p, n in zip(paths, names)), (), 0, "Example"),
        1800000000,
    )
    for path, name in zip(paths, names):
        state.detail(
            state.claim(1800000000),
            Page((), ("de-dub",), 0, name, episode_title=name),
            1800000000,
        )
    with state.db:
        state.db.execute(
            "INSERT INTO canonical_title VALUES(?,?,?,?,?,?,?)",
            (mid, tid, "tvdb", "123", "synthetic-v1", "reviewed", 1800000000),
        )
        store(
            state,
            tid,
            "digest",
            "matcher",
            1800000000,
            [
                CanonicalEpisode(2, 9, "First unique story"),
                CanonicalEpisode(2, 10, "Another distinct story"),
                CanonicalEpisode(2, 11, "The ending"),
            ],
        )
        assert apply(state, tid, 1800000000) == "matched"
        assert [
            tuple(r)
            for r in state.db.execute(
                "SELECT season,episode FROM canonical_episode ORDER BY episode"
            )
        ] == [(2, 9), (2, 10), (2, 11)]
        state.db.execute("DELETE FROM canonical_episode")
        store(
            state,
            tid,
            "digest",
            "matcher",
            1800000000,
            [
                CanonicalEpisode(2, 9, "First unique story"),
                CanonicalEpisode(3, 10, "Another distinct story"),
                CanonicalEpisode(2, 11, "The ending"),
            ],
        )
        apply(state, tid, 1800000000)
        # Mixed source seasons cannot prove a season-wide correspondence, but
        # three globally unique episode names still prove their own coordinates.
        assert [
            tuple(row)
            for row in state.db.execute(
                "SELECT season,episode FROM canonical_episode ORDER BY episode"
            )
        ] == [(2, 9), (3, 10), (2, 11)]
        state.db.execute("DELETE FROM canonical_episode")
        state.db.execute("UPDATE entity SET display_title='...' WHERE native_episode=3")
        store(
            state,
            tid,
            "digest",
            "matcher",
            1800000000,
            [
                CanonicalEpisode(2, 9, "First unique story"),
                CanonicalEpisode(2, 10, "Another distinct story"),
                CanonicalEpisode(2, 11, "..."),
            ],
        )
        apply(state, tid, 1800000000)
        assert (
            state.db.execute("SELECT count(*) FROM canonical_episode").fetchone()[0]
            == 2
        )
    state.close()


def test_observed_episode_annotation_is_source_specific_and_keeps_ambiguity(tmp_path):
    from catalog_worker.episode_matching import source_keys

    assert source_keys("A distinct story [Episode 001]", "aniworld.to") == (
        "a distinct story episode 001",
        "a distinct story",
    )
    assert source_keys("A distinct story [Episode 001]", "s.to") == (
        "a distinct story episode 001",
    )
    assert source_keys("Episode 001", "aniworld.to") == ()
    assert source_keys("A distinct story [Meaningful subtitle]", "aniworld.to") == (
        "a distinct story meaningful subtitle",
    )
    state = State(tmp_path / "state.sqlite", "aniworld.to")
    title = "/anime/stream/example"
    tid = title_id(state.provider, title)
    mid = mapping_id(state.provider, tid, "tvdb", "123")
    state.discover(Link(title, "Example"), 1800000000)
    state.db.execute(
        "INSERT INTO canonical_title VALUES(?,?,?,?,?,?,?)",
        (mid, tid, "tvdb", "123", "synthetic-v1", "reviewed", 1800000000),
    )
    for n in [1, 2]:
        path = title + f"/staffel-9/episode-{n}"
        state.db.execute(
            "INSERT INTO work(path,title_id,kind,due) VALUES(?,?,?,?)",
            (path, tid, "episode", 1800000000),
        )
        state.detail(
            dict(
                state.db.execute("SELECT * FROM work WHERE path=?", (path,)).fetchone()
            ),
            Page((), ("de-dub",), 0, None, episode_title=f"Same name [Episode {n:03}]"),
            1800000000,
        )
    with state.db:
        store(
            state,
            tid,
            "digest",
            "matcher",
            1800000000,
            [CanonicalEpisode(2, 4, "Same name")],
        )
        apply(state, tid, 1800000000)
        assert (
            state.db.execute("SELECT count(*) FROM canonical_episode").fetchone()[0]
            == 0
        )
    state.close()
