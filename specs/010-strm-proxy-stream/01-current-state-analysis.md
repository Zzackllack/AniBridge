# Current State Analysis

## Status

Draft

## Scope

Document the current STRM generation and resolver flow, networking stack, deployment topology, and database/migration posture as implemented today, with explicit file/line evidence and known unknowns.

## Last updated

2026-02-03

## STRM Generation Flow (Today)

1. Torznab emits STRM variants when `STRM_FILES_MODE` is set to `both` or `only`, producing a STRM-specific magnet variant tagged with `aw_mode=strm` (or `sto_mode=strm` for s.to). See `docs/src/api/torznab.md:37` and `docs/src/api/torznab.md:47`.
2. The qBittorrent shim parses the magnet payload and reads the optional `mode` field. If `mode` is present, it is passed into the download request payload. See `app/api/qbittorrent/torrents.py:63` and `app/api/qbittorrent/torrents.py:99`.
3. The scheduler routes requests with `mode="strm"` to `_run_strm`, which builds an episode descriptor, resolves a direct URL using provider fallback, and writes the resolved URL into a `.strm` file under `DOWNLOAD_DIR`. See `app/core/scheduler.py:189`, `app/core/scheduler.py:215`, and `app/core/scheduler.py:241`.
4. STRM file content is validated to be a single HTTP(S) URL plus a newline. See `app/utils/strm.py:8`.

## Episode Identity And Resolver Inputs

- Episode identity parameters (`slug`, `season`, `episode`, `language`, `site`) are carried through magnets and parsed in `/torrents/add`, then passed through to the scheduler. See `docs/src/api/torznab.md:33` and `app/api/qbittorrent/torrents.py:66`.
- Episodes are constructed via `build_episode`, which selects a site base URL from `CATALOG_SITE_CONFIGS` and uses slug/season/episode when no direct link is provided. See `app/core/downloader/episode.py:47` and `app/core/downloader/episode.py:61`.

## Provider Resolution And Fallback Behavior

- Direct URLs are obtained via `Episode.get_direct_link(provider, language)` from the `aniworld` library, with a preferred provider first and fallback across `PROVIDER_ORDER`. See `app/core/downloader/provider_resolution.py:42` and `app/core/downloader/provider_resolution.py:156`.
- Language availability checks are performed before attempting provider resolution. See `app/core/downloader/provider_resolution.py:126`.
- There is no persisted STRM-to-resolved-URL mapping in the current DB schema; only `Job`, `EpisodeAvailability`, and `ClientTask` tables exist. See `app/db/models.py:52` and `app/db/models.py:93`.

## Networking, Proxies, And Egress Assumptions

- AniBridge supports proxy configuration via `PROXY_*` environment variables and can apply those settings globally to process env for downstream libraries. See `app/config.py:20` and `app/infrastructure/network.py:95`.
- The proxy layer explicitly calls out that provider/CDN tokens can be IP-bound (e.g., `i=` and `asn=` parameters), and it aligns requests egress with `yt-dlp` when `PROXY_SCOPE=ytdlp` to avoid 403s from mismatched IPs. See `app/infrastructure/network.py:56`.
- Documentation warns that the in-app proxy is experimental and suggests using a full VPN or Gluetun sidecar for production stability. See `docs/src/guide/networking.md:8`.

## HTTP Server Stack And Streaming Patterns

- The FastAPI app wires routers for Torznab, qBittorrent, health, and legacy downloader endpoints. See `app/main.py:22` and `app/main.py:29`.
- The only streaming response in the current codebase is `StreamingResponse` used for SSE job events in `/jobs/{job_id}/events`. See `app/api/legacy_downloader.py:68` and `app/api/legacy_downloader.py:99`.
- There is no existing byte-proxy or HLS streaming endpoint in the codebase.

## Deployment And Ingress Topology (Repo Evidence)

- Default `docker-compose.yaml` exposes port 8000 and mounts `./data` into `/data` for persistent data and downloads. See `docker-compose.yaml:4` and `docker-compose.yaml:90`.
- The quickstart guide describes a Gluetun VPN sidecar pattern (`network_mode: service:gluetun`) and exposing AniBridge through Gluetun’s port mapping. See `docs/src/guide/quickstart.md:62` and `docs/src/guide/quickstart.md:85`.
- No reverse proxy (Nginx/Traefik) configuration is included in this repo; any such ingress is external to the repo and therefore unknown.

## Database And Migrations Posture

- The database is SQLite (`anibridge_jobs.db` under `DATA_DIR`) and is managed via SQLModel with Alembic migrations. See `app/db/models.py:133` and `app/db/migrations/versions/20260203_0001_initial_schema.py:1`.
- On startup, the app runs Alembic migrations when `DB_MIGRATE_ON_STARTUP=true`, otherwise it creates tables directly. See `app/core/lifespan.py:130`.
- The Docker entrypoint creates directories and adjusts permissions but does not delete the DB file. See `docker/entrypoint.sh:33`.

## Existing STRM/Proxy Specifications In Repo

- STRM refresh scaffolding and a proposed `StrmUrlMapping` table exist as prior spec notes. See `specs/004-strm-file-support/refresh-boilerplate.md:32`.
- The STRM proxy direction (proxy URL in `.strm`, no redirect, Range support, refresh-on-failure) is documented in `specs/006-fix-strm-files/context.md`. See `specs/006-fix-strm-files/context.md:9`.
- HLS-specific playlist rewrite behavior and proxy endpoints are documented in `specs/006-fix-strm-files/HLS-m3u8-context.md`. See `specs/006-fix-strm-files/HLS-m3u8-context.md:51`.

## Unknowns And Data Gaps (Must Be Resolved)

- The actual percentage of resolved STRM URLs that are HLS `.m3u8` versus direct MP4 streams is not recorded anywhere in the repo.
- Whether the resolver returns required request headers (e.g., `Referer`, `User-Agent`, cookies) in a structured way is not documented in the repo.
- The exact media server(s) in use (Jellyfin vs Emby vs Kodi) and their STRM/Range behaviors are not stated in the repo.
- The ingress topology in production (reverse proxy presence, buffering defaults, TLS termination) is not documented in this repo.
- Whether any current deployments rely on `PROXY_SCOPE=requests` or `PROXY_SCOPE=ytdlp` for link extraction is unknown.
- Operational constraints for caching (memory limits, multi-worker deployment, cache eviction expectations) are unknown.
