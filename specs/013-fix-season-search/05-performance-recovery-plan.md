# 013 Season Search - Performance Recovery Plan

## Why this plan exists

Observed behavior from runtime logs shows a severe season-search latency regression:

- Request started: `2026-02-16 01:19:50`
- Response returned: `2026-02-16 01:21:47`
- Total wall time: ~117 seconds for an 18-episode season (`s.to`, season 2 of `9-1-1`).

Primary bottleneck: season-search currently performs expensive per-episode/per-language live probes (including provider iteration + `yt-dlp` quality extraction), which multiplies network work dramatically.

## Goals

- Make `tvsearch` season-search return quickly enough for Sonarr timeout windows.
- Keep episode-search (`season + ep`) behavior accurate and unchanged by default.
- Preserve response schema compatibility.

## Preferred approach

Use a **fast season-search path** as the default for `tvsearch` requests where `season` is present and `ep` is omitted.

### Fast-path design

1. Discover episode numbers using metadata and/or provider season enumeration (already fast enough in logs).
2. Build an episode-language availability matrix using lightweight provider-native signals (HTML/API page parsing), not `probe_episode_quality` for every row.
3. Generate Torznab items immediately from that matrix.
4. Reuse cached quality/provider fields when available.
5. If quality is missing, emit with fallback quality defaults rather than blocking on live probe.

### Keep strict path available

- Keep the existing strict probe behavior behind a mode switch for debugging or high-accuracy use cases.
- Suggested env flag:
  - `TORZNAB_SEASON_SEARCH_MODE=fast|strict` (default `fast`).

## Additional guardrails

- Add a request-time budget for season-search (for example 8-12 seconds).
- If budget is exceeded, return partial results rather than an empty timeout outcome.
- Keep `limit` as hard cap on emitted `<item>` rows.

## Implementation phases

## Phase 1 (hotfix)

- Default season-search to fast mode.
- Skip live quality probing in season mode when cache is empty.
- Return items based on discovered episode/language availability only.

## Phase 2 (quality stabilization)

- Add background cache warming (optional) to enrich quality/provider for future searches.
- Improve provider-native parsers for language/provider detection quality.

## Phase 3 (operational hardening)

- Add structured metrics/logs:
  - discovery duration
  - item generation duration
  - number of live probes (target near-zero in fast season mode)
  - timeout/budget cutoffs

## Acceptance criteria

- 18-episode season-search completes in Sonarr without timeout.
- Typical season-search response latency moves from minutes to low seconds.
- Episode-search semantics remain unchanged.
- No schema changes to Torznab XML.
