---
title: Configuration
outline: deep
---

# Configuration

AniBridge is configured via environment variables (works well with Docker). Sensible defaults are applied for local use.

> [!TIP]
> Paths are created if missing. On Docker, defaults map to `/data/...`; on bare metal they map to `./data/...` under the working directory.

## Core Paths

- `DOWNLOAD_DIR`: final download directory
- `DATA_DIR`: persistent data directory (SQLite DB, logs, cache)
- `QBIT_PUBLIC_SAVE_PATH`: path override in qBittorrent API responses (useful for container path mapping)

## Torznab

- `INDEXER_NAME` (default: `AniBridge Torznab`)
- `INDEXER_API_KEY` (optional; if set, `apikey` is required)
- `TORZNAB_CAT_ANIME` (default: `5070`)
- Fake peers for connectivity: `TORZNAB_FAKE_SEEDERS` / `TORZNAB_FAKE_LEECHERS`
- Connectivity test result: `TORZNAB_RETURN_TEST_RESULT` (`true|false`)
- Test release fields: `TORZNAB_TEST_TITLE`, `TORZNAB_TEST_SLUG`, `TORZNAB_TEST_SEASON`, `TORZNAB_TEST_EPISODE`, `TORZNAB_TEST_LANGUAGE`

## Provider & Language

- `PROVIDER_ORDER`: comma-separated providers by priority (e.g., `VOE,Filemoon,Streamtape,...`)
- Languages supported: `German Dub`, `German Sub`, `English Sub`

## Titles & Alternatives

- `ANIWORLD_ALPHABET_URL` (default: `https://aniworld.to/animes-alphabet`)
- `ANIWORLD_ALPHABET_HTML` (fallback local HTML snapshot path)
- `ANIWORLD_TITLES_REFRESH_HOURS` (TTL for in-memory cache)

## Naming

- `SOURCE_TAG` (e.g., `WEB`, `WEB-DL`)
- `RELEASE_GROUP` (e.g., `aniworld` -> becomes `-ANIWORLD`)

## Scheduler

- `MAX_CONCURRENCY` (thread pool size; default `3`)

## Networking / Proxy

- `PROXY_ENABLED` (default: `false`)
- `PROXY_URL` (common proxy URL; e.g., `socks5h://127.0.0.1:1080`)
- `HTTP_PROXY_URL`, `HTTPS_PROXY_URL`, `ALL_PROXY_URL` (overrides)
- `PROXY_HOST`, `PROXY_PORT`, `PROXY_SCHEME` (builds `PROXY_URL` when empty)
- `PROXY_USERNAME`, `PROXY_PASSWORD` (credentials; injected into proxy URLs if missing)
- `NO_PROXY` (CSV list of hosts to bypass)
- `PROXY_FORCE_REMOTE_DNS` (use `socks5h` for remote DNS)
- `PROXY_DISABLE_CERT_VERIFY` (disable TLS verify for requests)
- `PROXY_APPLY_ENV` (export HTTP(S)_PROXY/NO_PROXY to environment)
- `PROXY_IP_CHECK_INTERVAL_MIN` (minutes; periodically logs current public IP)

See the dedicated [Networking & Proxies](/guide/networking) guide for examples.

## Example `.env`

```ini
DOWNLOAD_DIR=./data/downloads/anime
DATA_DIR=./data
INDEXER_NAME="AniBridge Torznab"
TORZNAB_RETURN_TEST_RESULT=true
PROVIDER_ORDER=VOE,Filemoon,Streamtape,Vidmoly,SpeedFiles,Doodstream,LoadX,Luluvdo,Vidoza
SOURCE_TAG=WEB
RELEASE_GROUP=aniworld
MAX_CONCURRENCY=3
```

Browse the full list with explanations in [Environment](/api/environment).
