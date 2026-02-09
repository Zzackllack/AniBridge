# 012 Specials/Extras via Sonarr - Implementation Checklist

## Phase 1 (core fix)

- [ ] Add AniWorld specials parser (`/filme` page) with tests using provided Kaguya HTML fixture.
- [ ] Add special-title matcher with deterministic scoring and confidence threshold.
- [ ] Integrate matcher into `t=search` before preview fallback.
- [ ] For matched special, probe `season=0`, `episode=film_index` and emit targeted releases.
- [ ] Ensure release title for matched specials includes `SxxEyy` (no omission).
- [ ] Add unit tests for title formatting and matching behavior.
- [ ] Add integration test for Sonarr-like special title query returning episode-specific releases.

## Phase 1.5 (request-quality improvements)

- [ ] Expand Torznab caps `tv-search` supported params to include ID fields.
- [ ] Parse optional `tvdbid/tmdbid/imdbid/rid/tvmazeid` query params.
- [ ] Improve request logging to include ID params and mapping decisions.

## Phase 2 (robust mapping)

- [ ] Add metadata-backed resolver interface (feature flag).
- [ ] Implement first provider (prefer Sonarr-compatible source) with cache and timeout.
- [ ] Use metadata titles to map `tvsearch` alternate numbering to AniWorld film entries.
- [ ] Add fallback chain: metadata -> heuristic -> no-match.
- [ ] Add tests for mismatch scenario (`AniWorld film-4` vs Sonarr `S00E05`/scene alias).

## Phase 3 (observability and hardening)

- [ ] Add structured debug logs for: parser output, match scores, chosen mapping, rejected candidates.
- [ ] Add metric counters (matched/unmatched/ambiguous specials queries).
- [ ] Add docs section under `docs/agents/api.md` describing special/extras matching behavior.

## Acceptance criteria

- [ ] A Sonarr special title search returns release names with episode tokens (`SxxEyy`) instead of generic preview names.
- [ ] AniBridge can resolve AniWorld `/filme` entries for at least the provided Kaguya sample.
- [ ] No regression for normal non-special `tvsearch` and `search` flows.
