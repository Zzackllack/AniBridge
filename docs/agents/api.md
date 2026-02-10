# API Contracts

## Base URLs

- Local default: `http://localhost:8000`
- Docker mapping configured via `docker-compose.yaml` (port 8000)

## Health Endpoint (`/health`)

- Method: GET
- Response: JSON with `status`, `database`, `scheduler`, `download_dir`, `version`, `runtime`

## Torznab Namespace (`/torznab/api`)

- Supports `t=caps`, `t=search`, `t=tvsearch`, `t=movie`, `t=movie-search`.
- Returns XML responses conforming to Torznab spec.
- Accepts `apikey` when configured (`INDEXER_API_KEY`).
- `tvsearch` accepts ID hints: `tvdbid`, `tmdbid`, `imdbid`, `rid`, `tvmazeid`.
- Uses `title_resolver` and `EpisodeAvailability` cache for slug matching.
- For AniWorld specials/extras, applies metadata-backed alias/source mapping so Sonarr numbering can differ from AniWorld `film-N` ordering.

## qBittorrent Shim (`/api/v2/*`)

- Auth: `/auth/login`, `/auth/logout` set `SID` cookie `anibridge`.
- Categories: `/torrents/categories` returns configured categories (default `AniBridge`).
- Torrents: `/torrents/add`, `/torrents/delete`, `/torrents/info` mimic qBittorrent responses.
- Sync: `/sync/maindata` exposes job states for Sonarr integration.
- Transfer: `/transfer/info`, `/transfer/speedLimitsMode`, etc., return safe defaults.
- Deletion endpoint optionally removes files when `DELETE_FILES_ON_TORRENT_DELETE` is true.

## Legacy Downloader (`/downloader/download`)

- Backward-compatible endpoint that triggers downloads via scheduler.

## Response Models

- Many endpoints return `PlainTextResponse` (`Ok.`) to mirror qBittorrent semantics.
- JSON responses use Pydantic models or inline dictionaries defined per module.

## Error Handling

- Exceptions logged via Loguru.
- API returns structured errors aligned with qBittorrent/Torznab expectations.
- `app/api/qbittorrent/common.py` provides shared error helpers.
