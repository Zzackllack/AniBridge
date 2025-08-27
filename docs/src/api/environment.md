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

