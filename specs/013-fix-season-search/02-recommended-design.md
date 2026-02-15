# 013 Season Search - Recommended Design

## Goals

- Return multi-episode results for Sonarr season searches.
- Preserve existing single-episode behavior for `tvsearch` when `ep` is provided.
- Keep Torznab response schema unchanged.
- Bound latency and probe volume.

## Request mode semantics

Define two explicit `tvsearch` modes:

1. `episode-search` mode

- Condition: `season` and `ep` both provided.
- Behavior: current behavior (one requested episode path).

2. `season-search` mode

- Condition: `season` provided and `ep` omitted.
- Behavior: enumerate episode numbers for that season and emit results per episode.

This replaces current fallback-to-`ep=1` behavior.

## Season-search episode discovery (Option D)

Use this discovery order:

1. Metadata episode list (preferred)

- Resolve show metadata using existing ID/query flow.
- Collect episode numbers for the requested season.
- Deduplicate and sort ascending.

2. Cache hints

- Include episode numbers already seen in local availability cache for same `(slug, season, site)`.
- Merge with metadata list.

3. Bounded probing fallback

- If no episode numbers are discovered from metadata/cache, probe sequentially from `E01`.
- Stop at configurable guardrails (max episode attempts and consecutive misses).

## Per-episode item generation

For each discovered episode number:

1. Resolve candidate languages for that episode:

- First: cached available languages for `(slug, season, episode, site)`.
- Fallback: site default languages.

2. For each language:

- Reuse existing availability cache -> probe -> upsert flow.
- Reuse existing specials mapping behavior where applicable.
- Build release title and magnet exactly as today.
- Emit standard and STRM variants based on `STRM_FILES_MODE`.

## Limit behavior

Current global `limit` is item-based and can prematurely stop a season search if multiple language variants are emitted.

Define explicit behavior:

- `limit` remains a hard cap on returned `<item>` elements for compatibility.
- Add debug logging when season search exits due to `limit`.
- Document that high-episode or multi-language seasons may need higher `limit`.

## New helper surfaces

Add lightweight helpers to keep API handler readable:

- `list_cached_episode_numbers_for_season(session, slug, season, site) -> list[int]`
- `resolve_season_episode_numbers(...) -> list[int]` (metadata + cache + fallback orchestration)
- `emit_tvsearch_episode_items(...) -> int` (one episode, existing logic extraction)

No response schema change required.

## Configuration (proposed)

Add optional env vars:

- `TORZNAB_SEASON_SEARCH_MAX_EPISODES` (default: `60`)
- `TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES` (default: `3`)

If these are added, update `.env.example` in the implementation PR.

## Logging and observability

Add structured debug logs for:

- request mode (`episode-search` vs `season-search`)
- episode discovery source (`metadata`, `cache`, `fallback-probe`)
- episode count discovered
- termination reason (`limit hit`, `max episodes`, `consecutive misses`)

## Backward compatibility

- No change to `caps` output is required.
- No change to magnet schema is required.
- Existing `tvsearch` with explicit `ep` remains unchanged.
