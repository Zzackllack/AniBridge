---
title: Environment Variables
outline: deep
---

# Environment Variables

Comprehensive list of env vars read in `app/config.py`.

## Paths

- `DOWNLOAD_DIR`: where files are written
- `DATA_DIR`: where the SQLite DB and logs live
- `QBIT_PUBLIC_SAVE_PATH`: path override reported to clients (e.g., Sonarr)

## Indexer (Torznab)

- `INDEXER_NAME` (default: `AniBridge Torznab`)
- `INDEXER_API_KEY` (optional; requires `apikey`)
- `TORZNAB_CAT_ANIME` (default: `5070`)
- `TORZNAB_CAT_MOVIE` (default: `2000`)
- `TORZNAB_FAKE_SEEDERS` (default: `999`)
- `TORZNAB_FAKE_LEECHERS` (default: `787`)
- `TORZNAB_RETURN_TEST_RESULT` (`true|false`)
- `TORZNAB_TEST_TITLE` (default: `AniBridge Connectivity Test`)
- `TORZNAB_TEST_SLUG` (default: `connectivity-test`)
- `TORZNAB_TEST_SEASON` (default: `1`)
- `TORZNAB_TEST_EPISODE` (default: `1`)
- `TORZNAB_TEST_LANGUAGE` (default: `German Dub`)

## STRM Files

- `STRM_FILES_MODE` (`no|both|only`, default: `no`) — controls whether
  Torznab emits STRM variants and whether AniBridge creates `.strm` files
  instead of downloading media.
- `STRM_PROXY_MODE` (`direct|proxy|redirect`, default: `direct`) — when
  `proxy`, `.strm` files contain AniBridge proxy URLs instead of provider/CDN
  URLs (redirect behaves like proxy streaming).
- `STRM_PUBLIC_BASE_URL` (required for proxy mode) — public base URL used to
  build stable STRM proxy URLs. Use HTTPS when your media server is HTTPS to
  avoid mixed content blocking in browser clients.
- `STRM_PROXY_AUTH` (`none|token|apikey`, default: `token`) — auth mode for
  STRM proxy endpoints.
- `STRM_PROXY_SECRET` — shared secret for HMAC token signing or API key mode
  (required when auth is not `none`).
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
- Supported languages: `German Dub`, `German Sub`, `English Sub`, `English Dub`, `Deutsch` (megakino)

## Title Resolution

- `CATALOG_SITES` (default: `aniworld.to,s.to,megakino`)
- `ANIWORLD_BASE_URL` (default: `https://aniworld.to`)
- `ANIWORLD_ALPHABET_URL` (default: `https://aniworld.to/animes-alphabet`)
- `ANIWORLD_ALPHABET_HTML` (local fallback file)
- `ANIWORLD_TITLES_REFRESH_HOURS` (TTL, default: `24`)
- `STO_BASE_URL` (default: `https://s.to`)
- `STO_ALPHABET_URL` (default: `https://s.to/serien-alphabet`)
- `STO_ALPHABET_HTML` (local fallback file)
- `STO_TITLES_REFRESH_HOURS` (TTL, default: `24`)
- `MEGAKINO_BASE_URL` (default: `https://megakino1.to`, auto-resolved at startup)
- `MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN` (minutes; default: `100`, 0 disables background checks)

## Naming

- `SOURCE_TAG` (default: `WEB`)
- `RELEASE_GROUP` (default: `aniworld`)
- `RELEASE_GROUP_ANIWORLD` (default: `RELEASE_GROUP`)
- `RELEASE_GROUP_STO` (default: `sto`)

## Scheduler

- `MAX_CONCURRENCY` (default: `3`)

## Networking / Proxy

- `PROXY_ENABLED` (default: `false`)
- `PROXY_URL` (common proxy URL used when protocol-specific vars are empty)
- `HTTP_PROXY_URL` (override HTTP proxy URL)
- `HTTPS_PROXY_URL` (override HTTPS proxy URL)
- `ALL_PROXY_URL` (alternative fallback for both protocols)
- `PROXY_HOST`, `PROXY_PORT`, `PROXY_SCHEME` (split fields to build `PROXY_URL` when it’s empty)
- `PROXY_USERNAME`, `PROXY_PASSWORD` (credentials injected into URLs when missing)
- `NO_PROXY` (comma-separated list of hosts to bypass proxy)
- `PROXY_FORCE_REMOTE_DNS` (true: upgrade `socks5://` to `socks5h://`)
- `PROXY_DISABLE_CERT_VERIFY` (true: disable TLS verification for requests)
- `PROXY_APPLY_ENV` (true: set HTTP(S)_PROXY/NO_PROXY in process env)
- `PROXY_IP_CHECK_INTERVAL_MIN` (minutes; log current public IP periodically)

## Public IP Monitor

- `PUBLIC_IP_CHECK_ENABLED` (default: `false`) — enable periodic public IP logging even when proxy is disabled (useful behind VPN/Gluetun).
- `PUBLIC_IP_CHECK_INTERVAL_MIN` (default: inherits `PROXY_IP_CHECK_INTERVAL_MIN`) — minutes between checks when `PUBLIC_IP_CHECK_ENABLED=true`.

## Server Bind / Dev

- `ANIBRIDGE_HOST` (default: `0.0.0.0`) — listen address.
- `ANIBRIDGE_PORT` (default: `8000`) — listen port.
- `ANIBRIDGE_RELOAD` (default: `false`) — enables Uvicorn reload (development only).
- `ANIBRIDGE_CORS_ORIGINS` (default: `*`) — allowed origins for browser-based clients (e.g. docs try-it-out).
  - `*`: allow all origins (default).
  - CSV list: allow only those origins (example: `http://localhost:5173,http://127.0.0.1:5173`).
  - `off`/`none`: disable CORS middleware entirely.
- `ANIBRIDGE_CORS_ALLOW_CREDENTIALS` (default: `true`) — whether to include `Access-Control-Allow-Credentials: true` when CORS is enabled with non-wildcard origins. Ignored when `ANIBRIDGE_CORS_ORIGINS=*` (credentials are always disabled for wildcard origins).

> [!WARNING]
> Proxy support is experimental. Use a full VPN (or a Gluetun sidecar in Docker) for stable production operation.
