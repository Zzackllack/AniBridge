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
- `TORZNAB_FAKE_SEEDERS` (default: `999`)
- `TORZNAB_FAKE_LEECHERS` (default: `787`)
- `TORZNAB_RETURN_TEST_RESULT` (`true|false`)
- `TORZNAB_TEST_TITLE` (default: `AniBridge Connectivity Test`)
- `TORZNAB_TEST_SLUG` (default: `connectivity-test`)
- `TORZNAB_TEST_SEASON` (default: `1`)
- `TORZNAB_TEST_EPISODE` (default: `1`)
- `TORZNAB_TEST_LANGUAGE` (default: `German Dub`)

## Providers & Languages

- `PROVIDER_ORDER` (CSV; priority-ordered)

## Title Resolution

- `ANIWORLD_ALPHABET_URL` (default: `https://aniworld.to/animes-alphabet`)
- `ANIWORLD_ALPHABET_HTML` (local fallback file)
- `ANIWORLD_TITLES_REFRESH_HOURS` (TTL, default: `24`)

## Naming

- `SOURCE_TAG` (default: `WEB`)
- `RELEASE_GROUP` (default: `aniworld`)

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

> [!WARNING]
> Proxy support is experimental. Use a full VPN (or a Gluetun sidecar in Docker) for stable production operation.
