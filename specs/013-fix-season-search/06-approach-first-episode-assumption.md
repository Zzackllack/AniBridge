# 013 Season Search - Approach: Probe First Episode and Assume for the Rest

## Idea

For season-search (`season` without `ep`):

1. Probe only the first episode (or first N episodes).
2. Assume the same language/provider/quality pattern for the remaining episodes.
3. Emit items for all discovered episodes based on that assumption.

## Why this is attractive

- Extremely fast compared with probing every episode-language combination.
- Minimal extra load on provider/CDN infrastructure.
- Likely avoids Sonarr indexer timeout for medium/large seasons.

## Pros

- Major performance gain with small implementation effort.
- Preserves per-episode item semantics expected by Sonarr.
- Can reuse existing code paths with limited refactoring.

## Cons

- High risk of false positives:
  - Some episodes miss one language while others have it.
  - Quality can vary episode to episode.
  - Provider availability can drift within a season.
- Can create stale/noisy search results in Sonarr if many assumed items are not truly available.
- Difficult to reason about correctness for specials, mid-season changes, and partial uploads.

## Risk profile

- Performance risk: low.
- Correctness risk: medium/high.

## Mitigations if adopted

- Probe first 2-3 episodes instead of only one.
- Mark assumptions as confidence-limited internally (for logs/metrics).
- Optionally run lazy verification in background and update cache.
- Restrict assumptions to language availability only; avoid assuming exact quality tier.

## Recommendation

Use only as a temporary fast fallback or as a guarded optimization, not as the sole long-term correctness strategy.
