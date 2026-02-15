# 013 Season Search - Approaches Comparison

## Option A: Minimal wildcard probing (sequential episodes)

## Description

When `t=tvsearch` has `season` but no `ep`, iterate episodes sequentially (e.g., `E01..E{N}`) by probing availability and emitting results until a stop condition is hit.

## Pros

- Smallest code change.
- No new provider-specific parser or data source required.
- Fastest path to first working fix.

## Cons

- Hard to know true season length without authoritative source.
- Risk of slow requests due to many probe calls.
- Needs heuristic stop rules (consecutive misses), which can fail on sparse numbering.

## Risk

Medium.

---

## Option B: Metadata-driven episode list (SkyHook/TVDB)

## Description

Use Sonarr-compatible metadata episode lists for the requested season, then probe each listed episode on provider side and emit results.

## Pros

- Deterministic episode list for Sonarr numbering.
- Avoids guesswork about season bounds.
- Good alignment with existing specials metadata flow.

## Cons

- Depends on external metadata availability/latency.
- Potential numbering mismatch on edge cases where provider differs.
- Requires fallback path if metadata lookup fails.

## Risk

Low/Medium.

---

## Option C: Provider-native season enumeration

## Description

Add provider APIs/parsers to list all episodes for a season directly from AniWorld/s.to pages, then probe and emit per episode.

## Pros

- Lowest dependency on external metadata services.
- Could be most accurate for provider-local numbering.
- Strong long-term architecture for provider features.

## Cons

- Highest implementation complexity.
- Requires new parser contracts and tests per provider.
- More maintenance burden when provider markup changes.

## Risk

Medium/High.

---

## Option D: Hybrid (metadata-first + bounded probing fallback)

## Description

Use metadata season episode list when available, otherwise fallback to bounded sequential probing with strict guardrails. Cache-derived hints can reduce probing cost.

## Pros

- Reliable in best case and resilient in metadata outage case.
- Incremental change; can ship quickly and evolve later.
- Compatible with current architecture and specials mapping.

## Cons

- More moving parts than single-strategy options.
- Requires careful guardrails to avoid long-running requests.
- Needs explicit observability to debug fallback behavior.

## Risk

Low/Medium.

---

## Decision matrix

- Correctness for Sonarr season search: `D` > `B` > `C` > `A`
- Delivery speed: `A` > `D` > `B` > `C`
- Operational resilience: `D` > `C` > `B` > `A`

## Recommendation

Choose **Option D**.

Rationale:

- It fixes the current blocker quickly.
- It remains functional when metadata is partially unavailable.
- It gives a path to later strengthen provider-native enumeration without redoing API semantics.
