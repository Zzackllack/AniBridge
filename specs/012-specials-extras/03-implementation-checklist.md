# 012 Specials/Extras via Sonarr - Implementation Checklist

## Phase 1 (core fix)

- [x] Add AniWorld specials parser (`/filme` page) with tests using provided Kaguya HTML fixture.
- [x] Add special-title matcher with deterministic scoring and confidence threshold.
- [x] Integrate matcher into `t=search` before preview fallback.
- [x] For matched special, probe `season=0`, `episode=film_index` and emit targeted releases.
- [x] Ensure release title for matched specials includes `SxxEyy` (no omission).
- [x] Add unit tests for title formatting and matching behavior.
- [x] Add integration test for Sonarr-like special title query returning episode-specific releases.

## Phase 1.5 (request-quality improvements)

- [x] Expand Torznab caps `tv-search` supported params to include ID fields.
- [x] Parse optional `tvdbid/tmdbid/imdbid/rid/tvmazeid` query params.
- [x] Improve request logging to include ID params and mapping decisions.

## Phase 2 (robust mapping)

- [x] Add metadata-backed resolver interface (feature flag).
- [x] Implement first provider (prefer Sonarr-compatible source) with cache and timeout.
- [x] Use metadata titles to map `tvsearch` alternate numbering to AniWorld film entries.
- [x] Add fallback chain: metadata -> no-match (Option C only; heuristic intentionally skipped).
- [x] Add tests for mismatch scenario (`AniWorld film-4` vs Sonarr `S00E05`/scene alias).

## Phase 3 (observability and hardening)

- [ ] Add structured debug logs for: parser output, match scores, chosen mapping, rejected candidates.
- [ ] Add metric counters (matched/unmatched/ambiguous specials queries).
- [ ] Add docs section under `docs/agents/api.md` describing special/extras matching behavior.

## Acceptance criteria

- [x] A Sonarr special title search returns release names with episode tokens (`SxxEyy`) instead of generic preview names.
- [x] AniBridge can resolve AniWorld `/filme` entries for at least the provided Kaguya sample.
- [x] No regression for normal non-special `tvsearch` and `search` flows.
