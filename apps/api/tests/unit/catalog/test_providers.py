from types import SimpleNamespace

from app.catalog.providers import _parse_aniworld_season_rows, _parse_sto_season_rows


def test_parse_aniworld_season_rows_uses_season_html_only():
    season = SimpleNamespace(
        season_number=1,
        are_movies=False,
        _html="""
        <tbody id="season1">
          <tr itemprop="episode" itemscope itemtype="http://schema.org/Episode">
            <td class="season1EpisodeID">
              <meta itemprop="episodeNumber" content="1" />
              <a itemprop="url" href="/anime/stream/demo/staffel-1/episode-1">Folge 1</a>
            </td>
            <td class="seasonEpisodeTitle">
              <a href="/anime/stream/demo/staffel-1/episode-1">
                <strong>Deutsch Titel</strong> - <span>English Title</span>
              </a>
            </td>
            <td>
              <a href="/anime/stream/demo/staffel-1/episode-1">
                <i class="icon VOE" title="VOE"></i>
                <i class="icon Filemoon" title="Filemoon"></i>
              </a>
            </td>
            <td class="editFunctions">
              <a href="/anime/stream/demo/staffel-1/episode-1">
                <img class="flag" src="/public/img/german.svg" title="Deutsch/German" />
                <img class="flag" src="/public/img/japanese-german.svg" title="Mit deutschem Untertitel" />
              </a>
            </td>
          </tr>
        </tbody>
        """,
    )

    episodes = _parse_aniworld_season_rows(season)

    assert len(episodes) == 1
    episode = episodes[0]
    assert episode.season == 1
    assert episode.episode == 1
    assert episode.relative_path == "/anime/stream/demo/staffel-1/episode-1"
    assert episode.title_primary == "Deutsch Titel"
    assert episode.title_secondary == "English Title"
    assert episode.media_type_hint == "episode"
    assert [item.language for item in episode.languages] == [
        "German Dub",
        "German Sub",
    ]
    assert episode.languages[0].host_hints == ["Filemoon", "VOE"]


def test_parse_sto_season_rows_extracts_episode_links_without_episode_pages():
    season = SimpleNamespace(
        season_number=2,
        _html="""
        <a href="/serie/demo/staffel-2/episode-1">Episode 1</a>
        <a href="https://s.to/serie/demo/staffel-2/episode-2">Episode 2</a>
        <a href="/serie/demo/staffel-2/episode-2">Episode 2 duplicate</a>
        """,
    )

    episodes = _parse_sto_season_rows(season)

    assert [(item.season, item.episode, item.relative_path) for item in episodes] == [
        (2, 1, "/serie/demo/staffel-2/episode-1"),
        (2, 2, "/serie/demo/staffel-2/episode-2"),
    ]
    assert all(item.languages == [] for item in episodes)
