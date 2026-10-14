# AniBridge Agent Guide

AniBridge is a FastAPI service that bridges AniWorld/Serienstream/megakino catalogs to Torznab and qBittorrent-compatible APIs for *arr automation.

Essentials

- Python runtime baseline: 3.14.
- Package manager: uv for Python dependencies.
- Repo-wide: do not commit artifacts under `data/`.
- Database: SQLite with Alembic migrations in `apps/api/app/db/migrations`.
- Use of Context7 for up-to-date external documentation.
- On change of any environment variable, update `apps/api/.env.example`.
- Keep upstream state under `ANIWORLD_INSTALL_FOLDER` (default
  `${DATA_DIR}/aniworld`); do not mutate process `HOME` for library imports.
- Keep the code vocabulary explicit: `providers/` means catalogue sites
  (`aniworld.to`, `s.to`, `megakino`), while direct video hosts belong under
  `apps/api/app/hosts/`.

Request API private pilot

- Shared identities/read contract/cache: `packages/catalog-core`; collector and
  bounded read-serving command: `apps/catalog-worker` (separate uv projects).
- Selected contract: `internal/specs/020-catalog-query-api-evaluation/IMPLEMENTATION.md`.
  This supersedes 019 client snapshot distribution only. Historical gate failures
  remain historical failures; no public default or remote deployment is approved.
- `CATALOG_CONFIG_FILE` is opt-in: absent keeps mainline routes; query mode supports
  configured AniWorld/Serienstream and optional Megakino. Local corrections precede
  canonical filtering.
- Search never crawls or extracts video. Jobs freeze source identity and resolve
  on the user's instance. Do not introduce snapshot client download machinery.
- Total collector/service storage is 30,000,000,000 bytes, including state, read
  catalog/staging, backups, logs and 1,000,000,000-byte runtime reserve.
- Collector/index worker minimum: 2 vCPU/2 GiB; recommended: 4 vCPU/4 GiB.
  Optional 6 GiB needs measured benefit. The old 2-vCPU/512-MiB private pilot
  is a constrained test profile, not a production ceiling. Local client target
  is 1 vCPU/512 MiB for metadata/search; whole-job peaks remain unverified there.
- Use disposable pilot volumes and `scripts/catalog/query_pilot/compose.yaml`;
  never mix those with a real installation. No query/IP access logs by default.
- Keep `EVIDENCE.md` current; synthetic/client/live extraction/import/playback
  proofs are distinct. The maintainer guide is `scripts/catalog/query_pilot/README.md`.
- Normal Linux collection/server and separate local-client commands are in
  `scripts/catalog/query_pilot/SERVER.md`; Megakino live language gaps remain explicit.
- Collector state v5 adds private matching evidence and clocks; upgrades retain
  no-overwrite pre-v4/pre-v5 backups. Season rows
  supply positive names/languages; missing or changed evidence keeps detail work.
  Admission defers outside fetch slots; parser children remain fresh and bounded.
  Provider-specific `provider_settings` live in the worker JSON, not API env vars.
- Confirmed pilot defects and production throughput requirements are tracked in
  `internal/specs/020-catalog-query-api-evaluation/ISSUES.md`. Local budget waits
  are not provider failures; tune collection from measured work efficiency and
  classified responses, while retaining storage bounds and explicit resource
  profiles. A daily full recrawl is not the maintenance model; search remains
  catalog-only. Background demand refresh is proposed, not implemented.
- The original AniWorld metadata/season-1 discovery is closed. The finite generated
  media acceptance handoff is `scripts/catalog/query_pilot/ACCEPTANCE.md`; its HTTP input hook is
  test-only and must never be installed in a normal deployment.

Common pitfalls

- The README of this repository is not at ./README.md but at ./.github/README.md.

Non-standard commands

- Tests: `cd apps/api && pytest`
- Format: `cd apps/api && ruff format app`
- Docs build (local): `pnpm --prefix docs run build`
- Docs build (Cloudflare/wrangler): `pnpm --prefix docs install --frozen-lockfile && pnpm --prefix docs run build`

More guidance

- [Overview](internal/agents/overview.md)
- [Architecture](internal/agents/architecture.md)
- [Repository Map](internal/agents/repo-map.md)
- [Domain Models](internal/agents/domain-models.md)
- [API Contracts](internal/agents/api.md)
- [Configuration](internal/agents/configuration.md)
- [Coding Standards](internal/agents/coding-standards.md)
- [Development Workflow](internal/agents/dev-workflows.md)
- [Testing](internal/agents/testing.md)
- [Deployment](internal/agents/deployment.md)
- [Docs Site](internal/agents/docs-site.md)
- [Release & CI](internal/agents/release-ci.md)
- [Security & Legal](internal/agents/security-legal.md)
- [Onboarding & Collaboration](internal/agents/onboarding-collaboration.md)
- [References](internal/agents/references.md)

Maintenance notice

- Update `AGENTS.md` and the relevant `internal/agents/*` files whenever changes would make agent guidance outdated.

October 11 catalog repair guidance

- Safe child reports distinguish enrichment/export/validation/locking/publication;
  do not add raw stderr, HTML, player URLs, query terms, IPs or credentials.
- Read summaries must be independently validated; failed providers cannot yield
  an empty successful query. Preserve last-good catalogs on publication failure.
- Serienstream subtitle labels establish subtitles only. Missing language/player
  evidence never deletes releases. Unavailable fingerprints are v4-compatible;
  retained language-removal quarantines require a separate explicit decision.
- Active/gap title and season parents share the existing 20% reconciliation
  budget; four-hour eligibility is not a whole-provider SLA. Retry deadlines win.
- Existing Coolify upgrade/rollback commands are in `scripts/catalog/query_pilot/SERVER.md`.
  All three worker image references must change together; retain volumes,
  configuration, network ranges and limits. The authorized October 11 rollout
  uses a pinned GHCR worker manifest, `pull_policy: missing`, and 2 CPU/2 GiB for
  the collector; metadata stays at 512 MiB. The local-image staging helper is
  historical. New deployment/restart/resource changes still require approval.
- October 14 mapping follow-up: use spec 020's `MAPPING_REPAIR.md` and
  `MAPPING_IMPLEMENTATION.md`. Prioritize correspondence gaps and unchanged-descriptor
  recheck demand; preserve conservative evidence and shared canonical admission.
  CI regression coverage supports this work and must not replace the fixes.

v3 integration

- `main` remains the default/stable branch; `v3` is the protected integration base.
- Default-branch and release-policy prerequisites are in
  `internal/releases/v3-transition.md`; do not infer readiness from a draft PR.
- Preview API/worker images use separate GHCR packages, actual source SHAs and
  native AMD64/ARM64 builds. Pin manifest digests for approved pilot rollouts;
  publishing a preview does not authorize deployment or a resource change.

October 14 implemented follow-up

- Descriptor acquisition and local correspondence have separate clocks. Stable
  descriptors use seven-day eligibility; recent meaningful unresolved names use
  daily eligibility. This is bounded background canonical work, not a freshness
  SLA, demand refresh or provider episode recrawl. Canonical admission defaults
  to a shared 30/minute budget; `limits.canonical_requests_per_minute` accepts
  4–120 for measured tuning. This is our safety budget, not a documented Skyhook
  quota. Changing it must not invalidate descriptors/matcher fingerprints.
  The subsequent approved pilot uses 90/minute on `d85ed05`; bounded 120/minute
  testing found no 403/429, not a discovered quota or sustained-capacity proof.
- Optional `canonical_sources.episode_languages: ["deu"]` uses verified Skyhook v2
  TVDB episode IDs and coordinates for translation joins. Legacy authority tags
  remain wire-compatible; private evidence records the actual API provenance.
- Runtime rejection/freshness diagnostics are bounded counts/IDs only. Required
  source names live solely in sanitized metadata test fixtures. Never accept from
  similarity, native numbering, generic names or a conflicting parent year/ID.
- State v5 code rollback removes only private matching tables after the canonical
  admission window expires. Keep all v4 observations/maps/history and both backup
  generations. Follow SERVER.md; new registry publication and rollout need approval.
- Frozen API/core/worker CI jobs and the always-running gate passed hosted CI on
  `2240b91`; matching native AMD64/ARM64 previews are published. Ruff checks must
  never rewrite reviewed branches. Protection enforcement remains separate from
  a successful check; `main` stays default. See the dated evidence for deployment
  status, and use the pinned upgrade/rollback rather than a moving preview tag.
