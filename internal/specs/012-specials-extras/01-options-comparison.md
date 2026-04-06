# 012 Specials/Extras via Sonarr - Options Comparison

## Option A: Heuristic title match on AniWorld `/filme` only

## Description

- Parse AniWorld `/filme` page.
- Match incoming `t=search&q=...` title tokens against parsed film/special entries.
- Return only matched entries instead of generic preview.

## Pros

- No external dependency.
- Fast to implement.
- Immediately improves title-only special searches.

## Cons

- Numbering mismatch remains (Sonarr may expect `S04E01` or `S00E05` while AniWorld is `film-4`).
- Hard to guarantee correct Sonarr mapping from title alone.
- Ambiguous titles can mis-map.

## Risk

Medium.

---

## Option B: Heuristic match + emit query-alias season/episode

## Description

- Same as Option A for selecting the AniWorld film entry.
- For `tvsearch` fallback cases, if Sonarr asked for `season=X,ep=Y`, emit release title using `SXXEYY` (query alias), but download via matched AniWorld `film-N` magnet metadata.

## Pros

- Works with Sonarr's actual request expectations.
- Avoids forcing AniWorld numbering onto Sonarr.
- No mandatory external metadata API.

## Cons

- Requires robust linking between search phases.
- If no good match exists, behavior falls back to current failure mode.

## Risk

Low/Medium.

---

## Option C: Metadata-backed mapping (recommended long-term)

## Description

- Add support for Sonarr ID params (`tvdbid`/`tmdbid`/etc.) by advertising and parsing them.
- Use metadata lookup (same numbering universe Sonarr uses) to map requested episode/title to canonical special numbering.
- Match canonical title against AniWorld `/filme` entries and produce mapped result.

## Pros

- Highest correctness for numbering mismatches.
- Handles edge cases where AniWorld ordering differs significantly.
- Better portability across series with complex specials ordering.

## Cons

- More moving parts (ID handling, metadata client, cache, fallback rules).
- Depends on external metadata availability/rate limits.

## Risk

Medium.

---

## Option D: Manual per-series mapping config

## Description

- Store custom mapping files for problematic series.

## Pros

- Deterministic for known problematic shows.

## Cons

- High maintenance.
- Not scalable.
- Operational burden.

## Risk

High operational cost.

## Recommendation

- Phase 1: Option B.
- Phase 2: Add Option C behind feature flag and make it default after validation.
- Keep Option D only as emergency override, not primary strategy.
