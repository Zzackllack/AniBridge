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
- `TORZNAB_CAT_MOVIE` (default: `2000`)
- Fake peers for connectivity: `TORZNAB_FAKE_SEEDERS` / `TORZNAB_FAKE_LEECHERS`
- Connectivity test result: `TORZNAB_RETURN_TEST_RESULT` (`true|false`)
- Test release fields: `TORZNAB_TEST_TITLE`, `TORZNAB_TEST_SLUG`, `TORZNAB_TEST_SEASON`, `TORZNAB_TEST_EPISODE`, `TORZNAB_TEST_LANGUAGE`

## STRM Files

- `STRM_FILES_MODE` (`no|both|only`, default: `no`)
  - `no`: behave like today (download via yt-dlp).
  - `both`: emit both variants for each Torznab item (download + STRM).
  - `only`: emit only STRM variants.
- `STRM_PROXY_MODE` (`direct|proxy|redirect`, default: `direct`)
- `STRM_PUBLIC_BASE_URL` (required when proxy mode is enabled)
- `STRM_PROXY_AUTH` (`none|token|apikey`, default: `token`)
- `STRM_PROXY_SECRET` (shared secret for token/apikey auth)
- `STRM_PROXY_UPSTREAM_ALLOWLIST` (comma-separated upstream host allowlist)
- `STRM_PROXY_CACHE_TTL_SECONDS` (default: `0`)
- `STRM_PROXY_TOKEN_TTL_SECONDS` (default: `900`)

When `STRM_PROXY_AUTH` is set to `token` or `apikey`, `STRM_PROXY_SECRET`
must be configured.

In STRM mode, AniBridge schedules creation of a `.strm` file (plain text,
one HTTP(S) URL line) instead of downloading media bytes. When
`STRM_PROXY_MODE=proxy`, the `.strm` file contains a stable AniBridge URL
that streams bytes from the upstream provider/CDN.

::: warning
Sonarr can occasionally reject `.strm` imports with “No audio tracks detected” even when playback works. If this
appears, use manual import or disable “Analyze video files” in Sonarr. See
[Issue #50](https://github.com/zzackllack/anibridge/issues/50).
:::

::: warning
Known limitation: when `STRM_PROXY_MODE=proxy`, some media players (especially Jellyfin with specific HLS sources)
may still show `Video-Bitrate: 0 kbps` and/or exhibit unstable playback behavior. There is currently no reliable
AniBridge-side fix planned in the near term for this class of issue. See [Issue #51](https://github.com/Zzackllack/anibridge/issues/51)
:::

## Provider & Language

- `PROVIDER_ORDER`: comma-separated providers by priority (e.g., `VOE,Filemoon,Streamtape,...`)
- Languages supported: `German Dub`, `German Sub`, `English Sub`, `English Dub`

## Catalogue Sites & Title Indices

- `CATALOG_SITES`: enabled catalogues (default `aniworld.to,s.to,megakino`). Order controls search priority.
- `ANIWORLD_BASE_URL`: AniWorld base URL (default `https://aniworld.to`).
- `ANIWORLD_ALPHABET_URL`: AniWorld alphabet page (default `https://aniworld.to/animes-alphabet`).
- `ANIWORLD_ALPHABET_HTML`: local AniWorld snapshot path (default `./data/aniworld-alphabeth.html`).
- `ANIWORLD_TITLES_REFRESH_HOURS`: AniWorld index refresh cadence (default `24`).
- `STO_BASE_URL`: Serienstream/s.to base URL (default `https://s.to`).
- `STO_ALPHABET_URL`: Serienstream alphabet page (default `https://s.to/serien-alphabet`).
- `STO_ALPHABET_HTML`: local Serienstream snapshot path (default `./data/sto-alphabeth.html`).
- `STO_TITLES_REFRESH_HOURS`: Serienstream index refresh cadence (default `24`).
- `MEGAKINO_BASE_URL`: megakino base URL (auto-resolved at startup; override if needed).
- `MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN`: minutes between background domain checks (default `100`, 0 disables).

Megakino base URLs are auto-resolved by loading `mirrors.txt` from known megakino domains and validating the sitemap until a working site is found.
Megakino operates in search-only mode (no alphabet index). Queries must use a slug or a URL that contains one (e.g. `/serials/<id>-<slug>.html`).
Megakino defaults to `Deutsch`/`German Dub` language labels; adjust `PROVIDER_ORDER` or query language if needed.

## Naming

- `SOURCE_TAG` (e.g., `WEB`, `WEB-DL`)
- `RELEASE_GROUP` (e.g., `aniworld` -> becomes `-ANIWORLD`)
- `RELEASE_GROUP_ANIWORLD` / `RELEASE_GROUP_STO`: per-catalogue overrides for release group suffix

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

> [!WARNING]
> Proxy support is experimental and may be unreliable with some providers/CDNs. Prefer a full VPN or Gluetun sidecar for production workloads.

See the dedicated [Networking & Proxies](/guide/networking) guide for examples and caveats.

## Example `.env`

```ini
CATALOG_SITES=aniworld.to,s.to,megakino
DOWNLOAD_DIR=./data/downloads/anime
DATA_DIR=./data
ANIWORLD_BASE_URL=https://aniworld.to
STO_BASE_URL=https://s.to
MEGAKINO_BASE_URL=https://megakino1.to
INDEXER_NAME="AniBridge Torznab"
TORZNAB_RETURN_TEST_RESULT=true
PROVIDER_ORDER=VOE,Filemoon,Streamtape,Vidmoly,SpeedFiles,Doodstream,LoadX,Luluvdo,Vidoza
SOURCE_TAG=WEB
RELEASE_GROUP=aniworld
RELEASE_GROUP_STO=sto
MAX_CONCURRENCY=3
```

Browse the full list with explanations in [Environment](/api/environment).
