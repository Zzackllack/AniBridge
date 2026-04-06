# 013 Season Search Returns Only One Episode - Current State and Evidence

## Reported issue

A user reported that Sonarr "Season Search" against AniBridge returns only one result (typically `SxxE01`) instead of one result per episode in the season. Sonarr then treats the season search as complete too early.

Reported environment:

- AniBridge version: `v2.4.3`
- OS: Linux
- Client: Sonarr (via Torznab)

## Reproduction summary

1. Add a series in Sonarr.
2. Trigger a season-level search.
3. Observe AniBridge Torznab results.
4. Only one episode appears.

## Expected behavior

For season-level searches, the Torznab response should contain one `<item>` per available episode in that season (and potentially multiple per episode when multiple release variants/languages exist).

## Current code-path evidence

The current `tvsearch` implementation explicitly converts a missing `ep` into `ep=1`:

- `app/api/torznab/api.py:944`
- `app/api/torznab/api.py:945`
- `app/api/torznab/api.py:946`

After that, the full execution path is episode-specific and only probes one `(season, episode)` pair:

- Episode/language loop anchored on one `ep_i`: `app/api/torznab/api.py:1014`
- Probe call for a single episode: `app/api/torznab/api.py:1059`
- Item generation for that same single episode: `app/api/torznab/api.py:1144`

This behavior matches the user report.

## Why this happens

The endpoint currently conflates two request shapes:

- Episode search: `season` + `ep` present
- Season search: `season` present, `ep` absent

Instead of treating `ep` as wildcard in the second case, it forces `ep=1` and returns only that episode's results.

## Existing building blocks we can reuse

- Per-episode availability probe exists: `app/utils/probe_quality.py:52`
- Availability cache exists (keyed by slug+season+episode+language+site): `app/db/models.py:471`
- Metadata and SkyHook integration exists in specials mapper and already uses cached remote lookups: `app/providers/aniworld/specials.py:371`

## Constraints

- Keep existing episode-specific `tvsearch` behavior unchanged when `ep` is provided.
- Avoid breaking specials mapping logic already present for AniWorld.
- Avoid excessive provider/network probing during season searches.
- Preserve current Torznab response schema and compatibility.

## Non-goals

- Redesign of generic `t=search` preview behavior.
- Changes to qBittorrent shim behavior.
- Changes to downloader naming/import flow unrelated to Torznab season search.
