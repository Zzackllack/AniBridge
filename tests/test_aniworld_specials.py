from app.providers.aniworld.specials import (
    AniworldSpecialEntry,
    SpecialIds,
    parse_filme_entries,
    resolve_special_mapping_from_episode_request,
    resolve_special_mapping_from_query,
)


def test_parse_filme_entries_extracts_season_zero_rows() -> None:
    html = """
    <table>
      <tbody id="season0">
        <tr data-episode-id="49981" data-episode-season-id="4">
          <td class="season0EpisodeID"><a href="/anime/stream/kaguya/filme/film-4">Film 4</a></td>
          <td class="seasonEpisodeTitle">
            <a href="/anime/stream/kaguya/filme/film-4">
              <strong>Kaguya title</strong> - <span>The First Kiss That Never Ends [Movie][Part 3]</span>
            </a>
          </td>
        </tr>
      </tbody>
    </table>
    """
    entries = parse_filme_entries(html)
    assert len(entries) == 1
    assert entries[0].film_index == 4
    assert entries[0].episode_id == 49981
    assert entries[0].episode_season_id == 4
    assert entries[0].title_alt == "The First Kiss That Never Ends [Movie][Part 3]"
    assert "Part 3" in entries[0].tags


def test_resolve_special_mapping_from_query_uses_metadata_alias(monkeypatch) -> None:
    entries = [
        AniworldSpecialEntry(
            film_index=4,
            episode_id=49981,
            episode_season_id=4,
            href="/anime/stream/kaguya/filme/film-4",
            title_de="Miyuki Shirogane Wants to Talk Things Over / Miko Iino Wants to Talk / About Kaguya Shinomiya",
            title_alt="The First Kiss That Never Ends [Movie][Part 3]",
            tags=("Movie", "Part 3"),
        )
    ]
    payload = {
        "tvdbId": 12345,
        "episodes": [
            {
                "seasonNumber": 0,
                "episodeNumber": 5,
                "title": "Miyuki Shirogane Wants to Talk Things Over / Miko Iino Wants to Talk / About Kaguya Shinomiya",
            }
        ],
    }

    monkeypatch.setattr(
        "app.providers.aniworld.specials.fetch_filme_entries",
        lambda slug, timeout_seconds=8.0: entries,
    )
    monkeypatch.setattr(
        "app.providers.aniworld.specials._resolve_show_payload",
        lambda **_kwargs: payload,
    )

    mapping = resolve_special_mapping_from_query(
        slug="kaguya-sama-love-is-war",
        query="Kaguya sama Love Is War Miyuki Shirogane Wants to Talk Things Over",
        series_title="Kaguya-sama: Love is War",
        ids=SpecialIds(),
    )
    assert mapping is not None
    assert mapping.source_season == 0
    assert mapping.source_episode == 4
    assert mapping.alias_season == 0
    assert mapping.alias_episode == 5


def test_resolve_special_mapping_from_episode_request_maps_requested_alias(
    monkeypatch,
) -> None:
    entries = [
        AniworldSpecialEntry(
            film_index=4,
            episode_id=49981,
            episode_season_id=4,
            href="/anime/stream/kaguya/filme/film-4",
            title_de="Miyuki Shirogane Wants to Talk Things Over / Miko Iino Wants to Talk / About Kaguya Shinomiya",
            title_alt="The First Kiss That Never Ends [Movie][Part 3]",
            tags=("Movie", "Part 3"),
        )
    ]
    payload = {
        "tvdbId": 12345,
        "episodes": [
            {
                "seasonNumber": 0,
                "episodeNumber": 5,
                "title": "Miyuki Shirogane Wants to Talk Things Over / Miko Iino Wants to Talk / About Kaguya Shinomiya",
            }
        ],
    }

    monkeypatch.setattr(
        "app.providers.aniworld.specials.fetch_filme_entries",
        lambda slug, timeout_seconds=8.0: entries,
    )
    monkeypatch.setattr(
        "app.providers.aniworld.specials._resolve_show_payload",
        lambda **_kwargs: payload,
    )

    mapping = resolve_special_mapping_from_episode_request(
        slug="kaguya-sama-love-is-war",
        request_season=0,
        request_episode=5,
        query="Kaguya-sama: Love is War",
        series_title="Kaguya-sama: Love is War",
        ids=SpecialIds(tvdbid=12345),
    )
    assert mapping is not None
    assert mapping.source_season == 0
    assert mapping.source_episode == 4
    assert mapping.alias_season == 0
    assert mapping.alias_episode == 5
