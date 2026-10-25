# Architecture

## Runtime Architecture Overview

- Entrypoint flow:
  1. `apps/api/app/main.py` calls bootstrap to load env vars and configure logging.
  2. FastAPI app created with custom lifespan (`apps/api/app/core/lifespan.py`).
  3. Routers for Torznab, qBittorrent, health, and legacy downloader attached.
  4. Lifespan initializes DB, scheduler, cleanup threads, public IP monitor, and update notifier.

- Layered structure:
  - API layer: `apps/api/app/api` exposes HTTP endpoints and validation.
  - Core services: `apps/api/app/core` manages bootstrap, scheduler, downloads.
  - Domain models: `apps/api/app/domain` defines domain data classes.
  - Persistence: `apps/api/app/db` manages SQLModel models and CRUD.
  - Infrastructure: `apps/api/app/infrastructure` handles logging, network diagnostics, system reports.
  - Utilities: `apps/api/app/utils` contains shared helpers.

## Request Lifecycle Example (Torznab Search)

1. Client hits `/torznab/api` with query parameters.
2. Router delegates to `apps/api/app/api/torznab/api.py`.
3. Title resolution uses `apps/api/app/utils/title_resolver.py`.
4. Providers queried via AniWorld library; results formatted to Torznab XML.
5. Response returned; job scheduling triggered if download requested.

## Download Lifecycle

- Jobs created in DB via `apps/api/app/db/models.create_job`.
- `apps/api/app/core/scheduler` manages a thread pool respecting `MAX_CONCURRENCY`.
- `apps/api/app/core/downloader` orchestrates video-host fallback and progress updates.
- Serienstream episode metadata uses the local v2 parser and configured
  verified origin. VOE uses the upstream pure HTML decoder behind a local
  bounded transport; default requests never launch a browser solver.
- `apps/api/app/hosts` wraps direct-video hosts (VOE, Filemoon, Streamtape,
  Vidmoly, Doodstream, LoadX, Luluvdo, Vidoza, GXPlayer) separately from
  catalogue-site providers.
- Completion updates job and client task states for qBittorrent shim.

## Download Pipeline and Video Hosts

- Video-host ordering is controlled by `PROVIDER_ORDER` (internally exposed as
  `VIDEO_HOST_ORDER` for clearer code-level naming).
- Quality probing uses `apps/api/app/utils/probe_quality.py` (yt-dlp metadata).
- Results stored under `DOWNLOAD_DIR`, optionally mapped to a public save path.
- TTL cleanup removes old downloads when `DOWNLOADS_TTL_HOURS` > 0.

## Scheduler & Background Services

- Thread pool size controlled by `MAX_CONCURRENCY` (default 3).
- Cleanup thread deletes downloads older than `DOWNLOADS_TTL_HOURS`.
- Public IP monitor runs only when `PUBLIC_IP_CHECK_ENABLED=true`.
- Lifespan ensures graceful shutdown of scheduler, DB engine, and background threads.

## Logging & Observability

- Loguru configuration lives in `apps/api/app/utils/logger.py`.
- `TerminalLogger` duplicates stdout/stderr to `data/terminal-YYYY-MM-DD.log`.
- `/health` endpoint provides liveness/readiness details.
- Update notifier logs when new GitHub releases are available.

## Private request metadata pilot

Selected contract: [020 implementation](../specs/020-catalog-query-api-evaluation/IMPLEMENTATION.md).
Collector parsing/ledger and indexed read code are shared without API startup
globals. The collector project's authenticated read command serves one compact
server catalog; local AniBridge fetches native batches and applies corrections
before policy, counts and pagination. Grabs retain source coordinates and run
locally. Client whole-file snapshot distribution is omitted. Mainline remains
the default until explicit query configuration. Public hosting is unapproved.

The October 14 worker follow-up keeps acquisition and local correspondence
separate: private v5 descriptors/IDs/fingerprints and durable admission support
verified cross-provider evidence reuse, while each provider retains its own
source identities and accepted maps. Public catalog/wire schemas remain unchanged.
Stable canonical evidence is eligible weekly; meaningful newly observed gaps
daily, under the shared 30/minute cap. This does not add demand refresh or search
scraping. See spec 020 MAPPING_IMPLEMENTATION.md for proof limits and remaining
missing/ambiguous evidence.

Publication uses generations and a bounded changed-title journal introduced in
private v6. The local v7 candidate adds per-work failure receipts; public schema2
is unchanged. Pre-v7 first-failure clocks remain unknown rather than backfilled.
The pilot server template mounts only configuration and published catalogs into
metadata serving. Read-catalog remains writable for reader leases; writer state
is absent. Existing live Compose is preserved by the update tool, so removing
its historical worker-state mount still needs an explicit reviewed live change.
Content changes retain their configured cadence; timestamp-only observations
have a separate eligibility interval. A verified previous schema2 artifact can
supply unchanged row-validation proofs; global admission checks still run. The
publisher refreshes changed partitions in private staging and switches the pointer
under the existing read lease. WAL snapshots let collection continue; acknowledgement
removes only captured generations. First publication and invalid bases use full
export/validation. No database engine, API wire schema or client migration changes.
