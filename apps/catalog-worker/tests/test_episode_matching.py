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
        assert (
            state.db.execute("SELECT count(*) FROM canonical_episode").fetchone()[0]
            == 0
        )
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
            == 0
        )
    state.close()
