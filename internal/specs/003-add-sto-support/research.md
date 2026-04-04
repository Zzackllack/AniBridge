# Research Summary – Dual Catalogue s.to Support

## Decision: Parallel catalogue fan-out
- **Rationale**: Keeps Torznab/qBittorrent latency within SC-001 (≤5 s) while ensuring no catalogue is skipped; aligns with clarifications favouring merged responses.
- **Alternatives considered**:
  - Sequential queries with early exit — lower load but risks missing slower catalogues and increases worst-case latency when the first catalogue has no match.
  - Sequential queries completing all catalogues — predictable ordering yet prolongs response time unnecessarily when parallelism is safe.

## Decision: Preserve existing FastAPI/Python/SQLite stack
- **Rationale**: User mandate to keep tech stack unchanged; complies with Operational Constraints section of constitution and avoids costly retooling.
- **Alternatives considered**:
  - Introduce additional databases (e.g., Postgres) — rejected due to complexity, deployment churn, and lack of demonstrated need.
  - Replace FastAPI with alternative frameworks — unnecessary; current stack already meets performance and ecosystem requirements.

## Decision: Maintain per-site availability caches and metadata
- **Rationale**: Prevents cross-site contamination when shows share names; maintains accuracy for episode counts and freshness.
- **Alternatives considered**:
  - Shared cache keyed only by slug — risks incorrect availability transfer between AniWorld and s.to.
  - Opportunistic cache reuse with heuristics — increases complexity and could misinform downstream automation.

## Decision: Surface both catalogue results ordered by configured priority
- **Rationale**: Gives Sonarr/Prowlarr full visibility and allows operators to choose preferred source while respecting configuration.
- **Alternatives considered**:
  - Return only highest-priority source — hides valid releases and may break workflows needing both.
  - Merge into a single composite entry — obscures provenance and complicates download management.
