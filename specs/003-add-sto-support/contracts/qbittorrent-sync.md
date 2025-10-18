# Contract: qBittorrent Shim `/api/v2/sync/maindata`

## Request
- **Method**: `GET`
- **Path**: `/api/v2/sync/maindata`
- **Headers/Cookies**: `SID=anibridge` session cookie (unchanged).
- **Query Parameters**:
  - `rid` (integer, optional) – same incremental sync token as today.

## Response
- **Content Type**: `application/json`
- **Structure adjustments**:
  - `torrents` object entries now include `anibridge_source_site` (string enum `aniworld`/`sto`).
  - Download metadata (name, progress, state, etc.) unchanged.
  - `categories` map may include site-aware defaults if operator defines them separately; baseline remains `"AniBridge": {"name": "AniBridge", "savePath": <configured path>}`.
- **Site assignment rule**: Each torrent inherits `source_site` from the originating `DownloadJob`. Legacy torrents without explicit source default to `aniworld`.

## Error Handling
- Authentication failures continue to return HTTP 403 with no body.
- Invalid `rid` continues to reboot the sync (full payload) without additional error fields.
