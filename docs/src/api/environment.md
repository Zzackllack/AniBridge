---
title: Environment Variables
outline: deep
---

# Environment Variables

Comprehensive list of env vars read in `apps/api/app/config.py` and
`apps/api/app/catalog/config.py`.

## Paths

- `DOWNLOAD_DIR`: where files are written
- `DATA_DIR`: where the SQLite DB and logs live
- `ANIWORLD_INSTALL_FOLDER`: isolated writable upstream configuration/session
  directory (default: `${DATA_DIR}/aniworld`)
- `QBIT_PUBLIC_SAVE_PATH`: path override reported to clients (e.g., Sonarr)

When running AniBridge from the checked-out source tree without overriding
these variables, local defaults are anchored to the repository root:

- `DATA_DIR` -> `<repo>/data`
- `DOWNLOAD_DIR` -> `<repo>/data/downloads`

AniBridge sets `ANIWORLD_INSTALL_FOLDER` before importing the upstream package
and does not change the process user's `HOME`. To reuse an existing trusted
upstream configuration, point this variable at that directory explicitly.

## Database

- `DB_MIGRATE_ON_STARTUP` (default: `true`): apply Alembic migrations at startup.
  Query mode requires `true`.

## qBittorrent Authentication

These settings protect `/api/v2` only. Configure all three together; partial
configuration refuses startup.

- `QBIT_USERNAME`: 1–256 bytes.
- `QBIT_PASSWORD`: at least 16 bytes.
- `QBIT_SESSION_SECRET`: at least 32 random bytes, independent of the password.
- `QBIT_COOKIE_SECURE` (default: `true`): emit secure session cookies for HTTPS
  ingress. Set `false` only for trusted private HTTP. A TLS proxy must preserve
  `Host`.

Sessions last one hour and survive restarts. Rotating the credentials or secret
invalidates existing sessions. Empty credentials keep unauthenticated
compatibility on a trusted private network.

## Indexer (Torznab)

- `INDEXER_NAME` (default: `AniBridge Torznab`)
- `INDEXER_API_KEY` (optional; requires `apikey`)
- `TORZNAB_CAT_ANIME` (default: `5070`)
- `TORZNAB_CAT_MOVIE` (default: `2000`)
- `TORZNAB_FAKE_SEEDERS` (default: `999`) / `TORZNAB_FAKE_LEECHERS`
  (default: `787`) — cosmetic counts for both legacy and query results. Negative
  values report zero; `peers` is their sum.
- `TORZNAB_RETURN_TEST_RESULT` (`true|false`) — legacy only. Query mode treats an
  empty `q` as a recent page.
- `TORZNAB_TEST_TITLE` (default: `AniBridge Connectivity Test`) — legacy only.
- `TORZNAB_TEST_SLUG` (default: `connectivity-test`) — legacy only.
- `TORZNAB_TEST_SEASON` (default: `1`) — legacy only.
- `TORZNAB_TEST_EPISODE` (default: `1`) — legacy only.
- `TORZNAB_TEST_LANGUAGE` (default: `German Dub`) — legacy only.
- `TORZNAB_SEASON_SEARCH_MODE` (`fast|strict`, default: `fast`) — legacy
  season-search execution mode. `fast` avoids live quality probing per episode.
- `TORZNAB_SEASON_SEARCH_MAX_EPISODES` (default: `60`) — legacy fallback probe
  ceiling when metadata/cache discovery has no episode list.
- `TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES` (default: `3`) — legacy fallback
  probe stop threshold for back-to-back missing episodes.
- `AVAILABILITY_TTL_HOURS` (default: `24`) — legacy availability cache TTL.

## Catalog Search Mode

- `CATALOG_MODE` (`legacy|query`, default: `legacy`; blank also means legacy) —
  selects live provider scraping or collector-backed metadata search. Legacy is
  deprecated but still functional.
- `CATALOG_API_URL` — query mode only. HTTPS origin root (no path, query,
  fragment, or userinfo) for the collector.
- `CATALOG_SOURCE_ID` — query mode only. Source identifier, 1–64 characters from
  `a-z`, `0-9`, `.`, `_`, and `-`.
- `CATALOG_API_TOKEN` / `CATALOG_API_TOKEN_FILE` — set exactly one in query mode.
  Tokens are 16–512 visible ASCII characters with no spaces. The file path is
  inside the API container; prefer a read-only mounted secret.
- `CATALOG_ALLOW_PRIVATE_HTTP` (default: `false`) — permits unencrypted HTTP to
  non-loopback hosts for trusted test networks. This does not enforce private IP
  addresses. Loopback HTTP is always allowed.
- `MANAGEMENT_API_TOKEN` — optional. Enables local `/api/v1/jobs/*` status,
  retry, and cancel endpoints. Must be base64url of at least 32 random bytes.
  Without it, management endpoints return 503.

`CATALOG_CONFIG_FILE` was removed. A non-empty value fails startup; migrate file
configuration to the environment variables above. The collector's JSON config is
separate (`apps/catalog-worker/config.example.json`) and is not read by the API.

There is no hosted zero-config metadata service yet. A future official public
catalog is planned; it has no approved endpoint. See
[Catalog Query Mode](/guide/catalog-query) for requirements, bounds, cache/stale
behavior, Filmo, numbering, and security boundaries.

## STRM Files

- `STRM_FILES_MODE` (`no|both|only`, default: `no`) — controls whether
  Torznab emits STRM variants and whether AniBridge creates `.strm` files
  instead of downloading media.
- `STRM_PROXY_MODE` (`direct|proxy|redirect`, default: `direct`) — when
  `proxy`, `.strm` files contain AniBridge proxy URLs instead of provider/CDN
  URLs (redirect behaves like proxy streaming).
- `STRM_PUBLIC_BASE_URL` (required for proxy mode) — public base URL used to
  build stable STRM proxy URLs.
- `STRM_PROXY_AUTH` (`none|token|apikey`, default: `token`) — auth mode for
  STRM proxy endpoints.
- `STRM_PROXY_SECRET` — shared secret for HMAC token signing or API key mode
  (required when proxy mode is enabled and auth is not `none`).
- `STRM_PROXY_UPSTREAM_ALLOWLIST` — comma-separated upstream host allowlist
  for proxying (optional).
- `STRM_PROXY_CACHE_TTL_SECONDS` (default: `0`) — TTL for resolved URL cache;
  `0` disables expiration.
- `STRM_PROXY_TOKEN_TTL_SECONDS` (default: `900`) — TTL for STRM proxy signed
  URL tokens.

::: warning
Sonarr can occasionally reject `.strm` imports with “No audio tracks detected” even when playback works. If this
appears, use manual import or disable “Analyze video files” in Sonarr. See
[Issue #50](https://github.com/zzackllack/anibridge/issues/50).
:::

## Providers & Languages

- `PROVIDER_ORDER` (CSV; priority-ordered)
- `PROVIDER_REDIRECT_TIMEOUT_SECONDS` (default: `12`)
- `PROVIDER_REDIRECT_RETRIES` (default: `2`)
- `PROVIDER_CHALLENGE_BACKOFF_SECONDS` (default: `300`) — suggested retry
  delay included in verification-required errors. AniBridge does not sleep in
  the worker or launch a browser to solve challenges.
- Supported language labels: `German Dub`, `German Sub`, `English Sub`,
  `English Dub`, and `Deutsch` (megakino). Per-site defaults differ: AniWorld
  uses German Dub/Sub and English Sub; s.to uses German Dub and English Dub;
  megakino uses Deutsch/German Dub. Filmo uses the audio languages declared by
  each offer and does not advertise unknown audio (`und`) as a known language.

## Title Resolution

- `CATALOG_SITES` (default: `aniworld.to,s.to,megakino`)
- `ANIWORLD_BASE_URL` (default: `https://aniworld.to`)
- `ANIWORLD_ALPHABET_URL` (default: `https://aniworld.to/animes-alphabet`)
- `ANIWORLD_ALPHABET_HTML` (local fallback file)
- `ANIWORLD_TITLES_REFRESH_HOURS` (TTL, default: `24`)
- `STO_BASE_URL` (default: `https://serienstream.to`)
- `STO_ALPHABET_URL` (default: `https://serienstream.to/serien?by=alpha`)
- `STO_ALPHABET_HTML` (local fallback file)
- `STO_TITLES_REFRESH_HOURS` (TTL, default: `24`)
- `MEGAKINO_BASE_URL` (default: `https://megakino1.to`, auto-resolved at startup)
- `MEGAKINO_TITLES_REFRESH_HOURS` (default: `12`)
- `MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN` (minutes; default: `100`, 0 disables background checks)
- `FILMO_BASE_URL` (default: `https://filmo.to`) — query mode only, and only
  when `filmo.to` is in `CATALOG_SITES`.

`CATALOG_SITES` order controls legacy search priority. Query mode merges collected
metadata by discovery time, so the legacy Megakino slug-only query rule does not apply. Filmo
requires `CATALOG_MODE=query`; legacy mode with Filmo configured fails startup.

## Naming

- `SOURCE_TAG` (default: `WEB`) — legacy naming only.
- `RELEASE_GROUP` (default: `aniworld`)
- `RELEASE_GROUP_ANIWORLD` (default: `RELEASE_GROUP`)
- `RELEASE_GROUP_STO` (default: `sto`)

## Scheduler, Progress & Cleanup

- `MAX_CONCURRENCY` (default: `3`) — parallel downloads. Query mode caps at two
  concurrent jobs regardless of a higher value.
- `DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC` (default: `0`, unlimited) — per-download
  yt-dlp bandwidth cap.
- `PROGRESS_FORCE_BAR` (default: `false`) — force the live progress bar when
  stdout is not a TTY.
- `PROGRESS_STEP_PERCENT` (default: `5`) — progress log step. Query jobs retain
  stepped lines in saved logs.
- `DELETE_FILES_ON_TORRENT_DELETE` (default: `true`) — delete the AniBridge-owned
  source file when the client deletes the torrent, after the final alias is
  removed.
- `DOWNLOADS_TTL_HOURS` (default: `0`, disabled) — delete old video files in
  `DOWNLOAD_DIR`. `.strm` files are not removed by TTL cleanup.
- `CLEANUP_SCAN_INTERVAL_MIN` (default: `30`) — cleanup scan interval.

A completed job stays completed when an importer moves or deletes the source.
Query mode reports `pausedUP`; legacy rows keep their completed projection. In
both cases progress stays `1`, `content_path` is empty, and
`anibridge_output_missing` is `true`; AniBridge does not report `missingFiles` or
rewrite the job to `failed`/`error`.

## Networking / VPN Policy

AniBridge does not provide an in-app outbound proxy anymore. Route traffic
externally using a host VPN, VPN sidecar, or network policy outside AniBridge.

## Public IP Monitor

- `PUBLIC_IP_CHECK_ENABLED` (default: `false`) — enable periodic public IP
  logging.
- `PUBLIC_IP_CHECK_INTERVAL_MIN` (default: `30`) — minutes between checks when
  `PUBLIC_IP_CHECK_ENABLED=true`.

## Server Bind / Dev

- `ANIBRIDGE_HOST` (default: `0.0.0.0`) — listen address.
- `ANIBRIDGE_PORT` (default: `8000`) — listen port.
- `ANIBRIDGE_RELOAD` (default: `false`) — enables Uvicorn reload (development only).
- `ANIBRIDGE_CORS_ORIGINS` (default: `*`) — allowed origins for browser-based clients (e.g. docs try-it-out).
  - `*`: allow all origins (default).
  - CSV list: allow only those origins (example: `http://localhost:5173,http://127.0.0.1:5173`).
  - `off`/`none`: disable CORS middleware entirely.
- `ANIBRIDGE_CORS_ALLOW_CREDENTIALS` (default: `true`) — whether to include `Access-Control-Allow-Credentials: true` when CORS is enabled with non-wildcard origins. Ignored when `ANIBRIDGE_CORS_ORIGINS=*` (credentials are always disabled for wildcard origins).

> [!IMPORTANT]
> Use external VPN routing for privacy and stable provider access (for example
> a system VPN or Gluetun sidecar).
