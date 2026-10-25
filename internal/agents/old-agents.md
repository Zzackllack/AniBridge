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
- Canonical lookup failures now emit `canonical_failure` with a hashed title ID,
  allowlisted phase/reason and optional HTTP status. Do not classify exceptions
  by their text. V2 TVDB descriptors may use either explicit episode ID/parent
  pair (`metadataId`/`metadataShowId` or `tvdbId`/`tvdbShowId`); incomplete or
  contradictory pairs stay rejected. This compatibility fix needs no state or
  matcher-version reset. See the October 18 evidence before inferring deployment.
  An optional translation with a verified series identity, no language tag and
  no episode names is unavailable evidence; retain the English descriptor and
  record `missing_languages` privately. Named untagged translations still reject.
- State v5 code rollback removes only private matching tables after the canonical
  admission window expires. Keep all v4 observations/maps/history and both backup
  generations. Follow SERVER.md; new registry publication and rollout need approval.
- Frozen API/core/worker CI jobs and the always-running gate passed hosted CI on
  `2240b91`; matching native AMD64/ARM64 previews are published. Ruff checks must
  never rewrite reviewed branches. Protection enforcement remains separate from
  a successful check; `main` stays default. See the dated evidence for deployment
  status, and use the pinned upgrade/rollback rather than a moving preview tag.

October 18 publication follow-up

- Private state v6 journals public changes transactionally, one pending row per
  title. Content uses `publish_interval_s`; observation/check timestamps alone
  use `publish_freshness_interval_s` (default 3600, range 300–86400 seconds,
  never faster than the content interval). This is eligibility, not a freshness SLA.
- Publication clones a digest-verified, previously admitted schema2 catalog and
  refreshes affected title partitions. Stale validator/policy receipts, tampering,
  unclassified changes or more than 1000 affected partitions require full rebuild.
  Full structural/integrity/relationship/semantic checks remain mandatory; only
  unchanged row-level proofs can be reused. Search and wire schemas are unchanged.
- Collection continues while the publication child pins a WAL snapshot. Only the
  captured generation is acknowledged; newer changes survive. Per-provider staging
  ownership and short read/publication leases remain separate from collection.
- Upgrade retains no-overwrite `.pre-v6.backup` as well as all older backups and
  `/state/backup`. A stopped-writer v6→v5 rollback uses `rollback_publication` from
  the new code, never a ledger restore. See SERVER.md before using an older image.
  These local changes do not imply a published image or live deployment.

October 19 episode annotation repair

- AniWorld finale announcements may append a confirmed next-season/start notice
  in English or German. The source-only fallback recognizes a closed annotation
  grammar; raw names, source coordinates and identities stay unchanged. Unknown
  brackets, duplicate names and conflicting aliases remain unresolved.
- Episode matcher v7 invalidates only local rematch receipts. Parent/descriptor
  fingerprints and canonical admission stay unchanged. A copied normal scheduler
  tick repaired Classroom S04E16 without network requests; unchanged follow-up
  work is skipped. See `evidence/finale-announcement-repair-2026-10-19.json` under
  spec 020. This local proof does not establish a live worker rollout.

October 19 worker upgrade

- The approved Zen cutover now runs `52065c7` at the immutable worker digest
  recorded in SERVER.md, with private v6 state and schema2 reads. All three
  worker references change together; original limits, configuration and volumes
  remain. Classroom S04E16 is verified through real Sonarr metadata search;
  this does not prove live media acquisition/import/playback.
- Repeat updates use `scripts/catalog/query_pilot/WORKER_UPDATES.md` and
  `prepare_worker_update.py`. CI/image selection and stopped-state snapshots/
  preservation checks are scripted; Coolify writes remain explicit through Zen.
  Do not follow moving `latest`/PR tags or broaden the read-only API token.
- Keep binary-export containers on `--log-driver none`; count all experiment
  copies and logs in disk admission. The archive preparation's transient log
  peak was not captured, so do not claim a measured under-cap peak for that phase.

October 20 canonical retry repair

- A cached local correspondence result cannot consume an expired canonical
  failure retry. Retry recovery may reuse a verified descriptor acquired after
  the failed attempt; older evidence cannot establish recovery. Backoff and
  existing maps remain intact. No matcher reset or state migration is needed.
- `--status` exposes `progress.canonical_queue` separately from provider page
  failures, including overdue cached retries and oldest scheduled retry age.
  These deadline counts are not an execution or freshness guarantee.
- `cached_retry_replay.py` compares bounded scheduler runs on marked, consistent
  disposable backups with simulated HTTP 500 responses. Keep before/after code,
  copies and resource profiles separate; no network or live ledger writer.
  See the October 20 evidence before inferring deployment or coverage gains.

October 24 local client progress/handoff repair

- Local transfers retain exact or explicitly estimated yt-dlp totals across
  selected tracks. Unknown future-track sizes remain unknown; no invented byte
  totals. The qBittorrent extension `anibridge_size_estimated` labels active
  estimates; 100% still requires verified output publication.
- Completion records a successful transfer, not permanent file ownership.
  Imported/missing outputs project `missingFiles` with no stale content path;
  startup does not rewrite completed jobs to failed or redownload them. Retain
  historical `missing_output` records; only explicit retry repeats a transfer.
- Both qBittorrent modes share missing-file semantics. Sync reads never invent
  completion timestamps or commit history changes. These changes need a local
  API rebuild; no collector/metadata worker upgrade or state migration is needed.
