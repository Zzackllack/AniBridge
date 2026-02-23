# 013 Season Search - Implementation Checklist

## Phase 1: Core behavior fix

- [ ] Remove `ep` defaulting to `1` in `tvsearch` when `ep` is missing.
- [ ] Add explicit `season-search` mode for `tvsearch` requests with missing `ep`.
- [ ] Extract current per-episode item generation into a reusable helper.
- [ ] Add season episode discovery helper (metadata -> cache -> fallback probing).
- [ ] Emit items for each discovered episode until `limit` is reached.

## Phase 2: Data and resilience

- [ ] Add DB helper for cached episode-number listing by season/site.
- [ ] Add fallback probing guardrails and config knobs.
- [ ] Add structured logs for discovery source and termination reason.

## Phase 3: Tests and docs

- [ ] Add unit tests for mode detection and discovery behavior.
- [ ] Add integration test proving multi-episode season search output.
- [ ] Verify existing specials and tvsearch tests remain green.
- [ ] Update Torznab docs for season-search semantics.
- [ ] Update `.env.example` for any new env vars.

## Acceptance criteria

- [ ] Sonarr season search receives multiple episode results for available episodes.
- [ ] Sonarr episode search (`season` + `ep`) behavior is unchanged.
- [ ] Empty/unavailable seasons return valid empty RSS (no errors).
- [ ] No regressions in existing Torznab tests.
