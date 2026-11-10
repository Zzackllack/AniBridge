from catalog_worker.mapping import (
    CanonicalEpisode,
    CanonicalTitle,
    match_episode,
    match_title,
)


def test_title_requires_unique_exact_known_year_and_type():
    one = CanonicalTitle("tvdb", "123", ("Example",), 2020, "series")
    other = CanonicalTitle("tvdb", "124", ("Example",), 2020, "series")
    assert match_title(("Example",), 2020, "series", (one,)) == (
        one,
        "exact_title_year",
    )
    assert match_title(("Example",), None, "series", (one,)) is None
    assert match_title(("Example",), 2020, "movie", (one,)) is None
    assert match_title(("Examples",), 2020, "series", (one,)) is None
    assert match_title(("Example",), 2020, "series", (one, other)) is None
    assert match_title(("Other label",), None, "series", (one,), ("tvdb", "123")) == (
        one,
        "explicit_id",
    )


def test_episode_never_assumes_season_or_ordinal_correspondence():
    episode = CanonicalEpisode(0, 7, "Special")
    assert match_episode("Special", 1, (episode,), {}) is None
    assert match_episode("Special", 1, (episode,), {1: 0}) == episode
    assert match_episode("Special", 1, (episode, episode), {1: 0}) is None
    assert match_episode("Other", 1, (episode,), {1: 0}) is None
