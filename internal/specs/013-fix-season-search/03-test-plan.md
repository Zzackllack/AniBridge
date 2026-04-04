# 013 Season Search - Test Plan

## Unit tests

1. Mode detection

- `tvsearch` with `season` + `ep` => `episode-search` path.
- `tvsearch` with `season` only => `season-search` path.

2. Episode discovery

- Metadata returns `[1,2,3]` => those episodes are used.
- Metadata empty + cache has `[1,2]` => cache episodes are used.
- Metadata/cache empty => fallback probing sequence until guardrail.

3. Guardrails

- Stops at `TORZNAB_SEASON_SEARCH_MAX_EPISODES`.
- Stops at `TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES`.

4. Limit handling

- Stops when `count >= limit` and logs reason.

## Integration tests (Torznab endpoint)

1. Season search emits multiple episodes

- Request: `t=tvsearch&q=...&season=1` (no `ep`).
- Assert: RSS contains multiple `<item>` entries with distinct episode numbers.

2. Episode search remains unchanged

- Request: `t=tvsearch&q=...&season=1&ep=1`.
- Assert: only requested episode behavior.

3. Metadata unavailable fallback

- Force metadata resolver failure.
- Assert: fallback probing still returns results when probe succeeds.

4. Empty season behavior

- No episodes available across discovery/probe.
- Assert: valid empty RSS response.

5. Specials safety

- Existing specials mapping tests continue to pass.

## Regression focus

- `t=search` preview behavior unaffected.
- `movie` / `movie-search` unaffected.
- STRM mode still emits corresponding variants.
