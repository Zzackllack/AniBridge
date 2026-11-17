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
- `ANIWORLD_INSTALL_FOLDER`: isolated upstream state directory (defaults to
  `DATA_DIR/aniworld`; does not replace or mutate `HOME`)
- `QBIT_PUBLIC_SAVE_PATH`: path override in qBittorrent API responses (useful for container path mapping)

## Search Mode: Legacy vs Catalog Query

Most installations should leave `CATALOG_MODE` blank. It selects where Torznab
search results come from:

- `legacy` (or unset/blank, the default): live provider scraping on each search.
  Deprecated but still functional for AniWorld, s.to, and megakino.
- `query`: search previously collected metadata from a collector you operate.
  Advanced/private preview; supports AniWorld, s.to, megakino, and optionally
  Filmo movies. Downloads remain local.

Query mode requires `CATALOG_API_URL` (HTTPS origin root), `CATALOG_SOURCE_ID`,
and exactly one of `CATALOG_API_TOKEN` or `CATALOG_API_TOKEN_FILE`, plus
`DB_MIGRATE_ON_STARTUP=true`. Complete configuration is required; legacy mode
rejects source settings instead of ignoring them. The JSON setting
`CATALOG_CONFIG_FILE` was removed and fails startup if non-empty. The collector's
own JSON config is separate.

There is no hosted, zero-config metadata catalog yet. A future official public
catalog is planned to remove user-entered metadata URLs and tokens; it has no
approved endpoint. Do not treat a private pilot URL or token as normal public
setup. See [Catalog Query Mode](/guide/catalog-query) for bounds, outage behavior,
numbering, Filmo, security boundaries, and preview/stable guidance.

## Torznab

- `INDEXER_NAME` (default: `AniBridge Torznab`)
- `INDEXER_API_KEY` (optional; if set, `apikey` is required)
- `TORZNAB_CAT_ANIME` (default: `5070`)
- `TORZNAB_CAT_MOVIE` (default: `2000`)
- Fake peers for connectivity: `TORZNAB_FAKE_SEEDERS` / `TORZNAB_FAKE_LEECHERS`
- Connectivity test result: `TORZNAB_RETURN_TEST_RESULT` (`true|false`)
- Test release fields: `TORZNAB_TEST_TITLE`, `TORZNAB_TEST_SLUG`, `TORZNAB_TEST_SEASON`, `TORZNAB_TEST_EPISODE`, `TORZNAB_TEST_LANGUAGE`
- Season-search mode:
  `TORZNAB_SEASON_SEARCH_MODE` (`fast|strict`, default: `fast`)
- Season-search fallback guardrails:
  - `TORZNAB_SEASON_SEARCH_MAX_EPISODES`
    (default: `60`)
  - `TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES`
    (default: `3`)

The connectivity test item and season-search tuning are legacy-only. Query mode
uses `t=caps` for connectivity and does not return a synthetic search item.

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

When proxy mode is enabled and `STRM_PROXY_AUTH` is `token` or `apikey`,
`STRM_PROXY_SECRET` must be configured. `redirect` is treated as `proxy`.

> [!IMPORTANT]
> If your media server is served over HTTPS, AniBridge should also be served over
> HTTPS for browser Direct Play. Set `STRM_PUBLIC_BASE_URL` to the HTTPS URL and
> place AniBridge behind a reverse proxy with TLS. The public URL must be
> reachable by both the media server and the client device.

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
- Provider requests use verified TLS and bounded redirects. A recognized
  challenge returns an actionable verification-required error; AniBridge does
  not start Patchright/Chromium automatically.
- Language labels: `German Dub`, `German Sub`, `English Sub`, `English Dub`, and
  `Deutsch`. Site defaults differ; Filmo uses each offer's declared audio tracks.

## Catalogue Sites & Title Indices

- `CATALOG_SITES`: enabled catalogues (default `aniworld.to,s.to,megakino`).
  Legacy mode uses order as search priority; query mode merges providers and
  sorts by discovery time.
- `ANIWORLD_BASE_URL`: AniWorld base URL (default `https://aniworld.to`).
- `ANIWORLD_ALPHABET_URL`: AniWorld alphabet page (default `https://aniworld.to/animes-alphabet`).
- `ANIWORLD_ALPHABET_HTML`: local AniWorld snapshot path (default `./data/aniworld-alphabeth.html`).
- `ANIWORLD_TITLES_REFRESH_HOURS`: AniWorld index refresh cadence (default `24`).
- `STO_BASE_URL`: Serienstream/s.to base URL (default `https://serienstream.to`).
- `STO_ALPHABET_URL`: Serienstream alphabet page (default `https://serienstream.to/serien?by=alpha`).
- `STO_ALPHABET_HTML`: local Serienstream snapshot path (default `./data/sto-alphabeth.html`).
- `STO_TITLES_REFRESH_HOURS`: Serienstream index refresh cadence (default `24`).
- `MEGAKINO_BASE_URL`: megakino base URL (legacy mode auto-resolves it at startup; override if needed).
- `MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN`: minutes between background domain checks (default `100`, 0 disables).
- `FILMO_BASE_URL`: Filmo origin used by query mode (default `https://filmo.to`).
  Only read when `filmo.to` is enabled in `CATALOG_SITES`.

Legacy Megakino is search-only (no alphabet index): queries must use a slug or a
URL containing one (for example `/serials/<id>-<slug>.html`). Query mode searches
collected Megakino metadata, so the legacy slug requirement does not apply.
Megakino defaults to `Deutsch`/`German Dub` labels.

Filmo is an optional movie provider for query mode only. Add `filmo.to` to
`CATALOG_SITES` and enable the same provider in the collector. Configuring Filmo
in legacy mode fails startup. Enabling Filmo does not create movie mappings on its
own: text discovery works without one, while Radarr ID searches and automatic
matching need a published `tmdb-movie` or `imdb` mapping. See
[Filmo](/integrations/providers/filmo).

## Naming

- `SOURCE_TAG` (e.g., `WEB`, `WEB-DL`) — legacy naming only. Query mode uses
  declared quality evidence from collected metadata.
- `RELEASE_GROUP` (e.g., `aniworld` -> becomes `-ANIWORLD`) — applies to both
  modes.
- `RELEASE_GROUP_ANIWORLD` / `RELEASE_GROUP_STO`: per-catalogue overrides for release group suffix

## Scheduler & Progress

- `MAX_CONCURRENCY` (parallel downloads; default `3`). Query mode caps at two
  concurrent jobs regardless of a higher value.
- `PROGRESS_FORCE_BAR` (default `false`): force the live progress bar when stdout
  is not a TTY.
- `PROGRESS_STEP_PERCENT` (default `5`): step size for progress log lines. Query
  jobs keep stepped lines in saved logs even when the bar is forced.

## Completed Downloads & Cleanup

- `DELETE_FILES_ON_TORRENT_DELETE` (default `true`): when Sonarr/Radarr deletes
  the torrent, also delete the AniBridge-owned source file after the final alias
  is removed. Set `false` to keep the source.
- `DOWNLOADS_TTL_HOURS` (default `0`, disabled): delete old video files in
  `DOWNLOAD_DIR`. `.strm` files are not removed by TTL cleanup.
- `CLEANUP_SCAN_INTERVAL_MIN` (default `30`): minutes between cleanup scans.

A completed job records publication, not permanent ownership of the file. If an
importer moves or deletes the source, AniBridge keeps the job completed (query
mode reports `pausedUP`; legacy rows keep their completed projection) with
progress `1` and `anibridge_output_missing: true`, and no `content_path`. It does
not turn that handoff into `failed`, `error`, or `missingFiles`.

## Networking / VPN Policy

In-app outbound proxy support has been removed. Use external routing only
(system VPN, Docker VPN sidecar, or network-layer policy outside AniBridge).

- `PUBLIC_IP_CHECK_ENABLED` (default: `false`) enables periodic public IP logs.
- `PUBLIC_IP_CHECK_INTERVAL_MIN` (default: `30`) controls the check interval;
  set `0` to disable.

See [Networking & VPN](/guide/networking) for supported patterns.

## Example `.env`

```ini
# Search: leave CATALOG_MODE blank for legacy, or set query for advanced use.
CATALOG_MODE=
CATALOG_SITES=aniworld.to,s.to,megakino
DOWNLOAD_DIR=./data/downloads
DATA_DIR=./data
ANIWORLD_INSTALL_FOLDER=./data/aniworld
ANIWORLD_BASE_URL=https://aniworld.to
STO_BASE_URL=https://serienstream.to
MEGAKINO_BASE_URL=https://megakino1.to
INDEXER_NAME="AniBridge Torznab"
TORZNAB_RETURN_TEST_RESULT=true
PROVIDER_ORDER=VOE,Filemoon,Streamtape,Vidmoly,Doodstream,LoadX,Luluvdo,Vidoza
SOURCE_TAG=WEB
RELEASE_GROUP=aniworld
RELEASE_GROUP_STO=sto
MAX_CONCURRENCY=3
DELETE_FILES_ON_TORRENT_DELETE=true
DOWNLOADS_TTL_HOURS=0
```

For query mode, add `CATALOG_API_URL`, `CATALOG_SOURCE_ID`, one token source,
and `DB_MIGRATE_ON_STARTUP=true`. See
[Catalog Query Mode](/guide/catalog-query#requirements).

Browse the full list with explanations in [Environment](/api/environment).
