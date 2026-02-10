# 012 Specials/Extras via Sonarr - Current State and Evidence

## Goal

Enable reliable discovery/import of AniWorld specials/extras (OVA, movie parts, special episodes) when Sonarr searches by special title and/or alternate season/episode mappings.

## Observed behavior in AniBridge logs

### 1) Sonarr first issues `t=search` with title-heavy query, no season/episode

In `/Users/zacklack/Developer/Own/Repos/AniBridge/data/terminal-2026-02-09_21-43-55-ee218387.log`:

- `153`, `346`, `531`, `716`: `t=search` requests with long special-title strings (e.g. `...Miyuki Shirogane Wants to Talk... Part 3`).

AniBridge currently routes these to `_handle_preview_search` (`app/api/torznab/api.py:55`) which:

- hardcodes probe target `season=1`, `episode=1` (`app/api/torznab/api.py:97`),
- intentionally omits `SxxEyy` from release title (`app/api/torznab/api.py:146-152`).

Result: generic series-level preview entries are returned, not the requested special episode.

### 2) Sonarr then issues `t=tvsearch` with mapped numbering

In the same log:

- `902`, `2583`, `4282`, `5963`: `t=tvsearch` with `season=4`, `ep=1` for this special search flow.

AniBridge then probes `S04E01` on AniWorld:

- `933`, `1483`, `2033`, ... probe attempts for `season=4`, `episode=1`.
- `936-940` and many repeats: no providers/streams on `.../staffel-4/episode-1`.
- `2580`, `4279`, `5960`, `7657`: RSS returned with `0` items.

### 3) Existing season-zero fix is present, but not sufficient for this case

- `app/core/downloader/episode.py:60` accepts `season is not None` (so `season=0` works).
- Tests already exist and pass for season-zero episode construction in `tests/test_downloader_episode.py`.

This fix helps when Sonarr requests `S00Exx` directly, but does not solve title-based special searches and scene-mapped alternate season numbering.

## AniWorld `/filme` structure evidence

From `/Users/zacklack/Developer/Own/Repos/AniBridge/data/Filme von Kaguya-sama_ Love is War _ AniWorld.to - Animes gratis legal online ansehen.html`:

- Film links are season-zero URLs (`/filme/film-1`, `/filme/film-2`, ...).
- A table body `id="season0"` contains rows with:
  - `data-episode-id`
  - `data-episode-season-id`
  - DE title in `<strong>` (optional)
  - EN/alt title in `<span>` (often with `[OVA]`, `[Movie][Part n]`, `[Special]`)

For Kaguya sample:

- `film-4`: `The First Kiss That Never Ends [Movie][Part 3]`
- `film-5`: `The First Kiss That Never Ends [Movie][Part 4]`
- `film-6/7`: `Stairway to Adulthood Part 1/2 [Special]`

So AniWorld has rich, parseable special metadata, but AniBridge does not currently use it during Torznab search resolution.

## Sonarr upstream behavior (source confirmation)

Using Sonarr source (`fdda9abc...`):

### Special search strategy

In `src/NzbDrone.Core/IndexerSearch/ReleaseSearchService.cs`:

- `SearchSpecial(...)` builds `EpisodeQueryTitles` as `"<series-title> <episode-title>"`.
- It dispatches a `SpecialEpisodeSearchCriteria` (title-only search path).
- It also triggers per-episode `SearchSingle(...)` fallback.

### Request generation for Newznab/Torznab

In `src/NzbDrone.Core/Indexers/Newznab/NewznabRequestGenerator.cs`:

- `GetSearchRequests(SpecialEpisodeSearchCriteria)` emits `t=search&q=...` only.
- `GetSearchRequests(SingleEpisodeSearchCriteria)` emits `t=tvsearch&season=...&ep=...`.
- Season `0` is encoded as `"00"` by `NewznabifySeasonNumber`.

Conclusion:

- The observed request pattern (title-only `search` first, then mapped `tvsearch`) matches Sonarr design.
- AniBridge must support both paths for reliable special matching.

## Why Sonarr and AniWorld numbering diverge

- AniWorld film index (`film-1..N`) is source-local ordering.
- Sonarr season/episode for specials can come from metadata + scene mappings.
- Therefore one-to-one `film-N -> S00EN` is not guaranteed.
- This mismatch is expected and must be resolved via title/metadata mapping, not assumed equal numbering.

## Import mismatch found after mapping fix (resolved)

From `/Users/zacklack/Developer/Own/Repos/AniBridge/data/sonarr/config/logs/sonarr.trace.txt`:

- Sonarr parsed the grabbed release as `S00E05` from title.
- AniBridge/qBittorrent state reported torrent `name` as `...S00E05...` but `content_path` as `...S00E04...`.
- During import, Sonarr parsed the file path (`S00E04`) and rejected with `Invalid season or episode`.

Root cause in AniBridge:

- Non-megakino download rename path still used source probe numbering (`aw_s/aw_e`) when building final filename.
- Alias numbering from Sonarr-facing release title (`title_hint`/`dn`) was not forwarded as `release_name_override` in this path.

Fix applied:

- `download_episode` now always derives `release_override` from `title_hint` (when present) and passes it to `rename_to_release` in both megakino and non-megakino flows.
- Result: grabbed release title numbering and final `content_path` numbering stay consistent, allowing Sonarr import to validate.

## Additional capability gap in AniBridge caps

Current caps in `app/api/torznab/utils.py`:

- `SUPPORTED_PARAMS = "q,season,ep"`
- no `tvdbid`, `tmdbid`, `imdbid`, `rid`, `tvmazeid` advertised.

Sonarr only sends ID-based `tvsearch` when caps advertise support. Without those params, AniBridge loses high-confidence identifiers that could improve mapping quality.

## External references used

- Sonarr Newznab request generation:
  - https://github.com/Sonarr/Sonarr/blob/fdda9abcbbce7de7e1c213dd7e524201fa53f319/src/NzbDrone.Core/Indexers/Newznab/NewznabRequestGenerator.cs
- Sonarr special search orchestration:
  - https://github.com/Sonarr/Sonarr/blob/fdda9abcbbce7de7e1c213dd7e524201fa53f319/src/NzbDrone.Core/IndexerSearch/ReleaseSearchService.cs
- Sonarr special criteria model:
  - https://github.com/Sonarr/Sonarr/blob/fdda9abcbbce7de7e1c213dd7e524201fa53f319/src/NzbDrone.Core/IndexerSearch/Definitions/SpecialEpisodeSearchCriteria.cs
- Sonarr metadata source implementation (SkyHook/TVDB):
  - https://github.com/Sonarr/Sonarr/blob/fdda9abcbbce7de7e1c213dd7e524201fa53f319/src/NzbDrone.Core/MetadataSource/SkyHook/SkyHookProxy.cs
