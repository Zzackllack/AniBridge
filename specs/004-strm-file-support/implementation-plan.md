# STRM File Support — Implementation Plan / Notes

## Feature toggle / behavior matrix

Env var: `STRM_FILES_MODE` (`no|both|only`, default `no`)

| Mode | Torznab results | qBittorrent shim action |
|---|---|---|
| `no` | unchanged (download items only) | unchanged (`yt-dlp` download jobs) |
| `both` | download item + STRM item per release | STRM item schedules `.strm` job |
| `only` | STRM items only | STRM items schedule `.strm` job |

## How STRM variants are transported

Torznab items continue to use magnet enclosures, but STRM variants add:

- `{prefix}_mode=strm` in magnet query params
- a different `xt=urn:btih:{hash}` so the “torrent hash” differs
- title suffix ` [STRM]` for human/UI disambiguation
- a normal-looking `enclosure length` (same heuristic sizing as non-STRM) so Sonarr/Prowlarr size filters don’t reject the release

## STRM job behavior

Input:

- slug/season/episode/language/site (+ optional provider)
- a display name (`title_hint`) from the magnet `dn` field

Steps:

1. Resolve `Episode` via AniWorld library (`build_episode()`).
2. Resolve a “direct URL” using the same provider fallback (`get_direct_url_with_fallback()`).
3. Write `.strm` file to `DOWNLOAD_DIR`:
   - safe basename derived from `title_hint`
   - extension `.strm`
   - content is one line containing the direct URL + newline
4. Mark job as completed with `result_path` pointing to `.strm`.

## Code touchpoints (current implementation)

- `app/config.py`
  - Add `STRM_FILES_MODE` parsing/validation.
- `app/utils/magnet.py`
  - Add optional `mode` parameter and include `{prefix}_mode` when set.
  - Make infohash depend on mode when provided (keeps legacy magnets stable).
- `app/api/torznab/api.py`
  - Emit STRM variants based on `STRM_FILES_MODE`.
  - Add ` [STRM]` suffix and `mode="strm"` magnets.
- `app/api/torznab/utils.py`
  - Allow overriding enclosure length/size (STRM uses small size).
- `app/api/qbittorrent/torrents.py`
  - Read `{prefix}_mode` and pass `mode` + `title_hint` into the scheduled job.
- `app/core/scheduler.py`
  - Route jobs with `mode="strm"` to a STRM runner that writes `.strm`.
- Docs / examples
  - `docs/src/api/environment.md`, `docs/src/guide/configuration.md`, `docs/src/api/torznab.md`
  - `.env.example`, `docker-compose.yaml`

## Validation checklist

- Default behavior:
  - With `STRM_FILES_MODE` unset (default `no`), Torznab output remains unchanged.
- Torznab variant behavior:
  - `both` yields two items per release; GUIDs and infohashes differ.
  - `only` yields only STRM items.
- Shim behavior:
  - Posting a magnet with `{prefix}_mode=strm` creates a `.strm` file in `DOWNLOAD_DIR`.
  - Job reaches `completed` and qBittorrent endpoints report the `.strm` path/size.

## Known gaps / future extensions

- Provide configurable STRM URL strategy:
  - `provider` direct URL (current)
  - `anibridge` streaming/proxy endpoint (range support)
  - user templated URL (remote file host)
- Decide how STRM interacts with:
  - Sonarr import rules (do we need a different file extension, or a post-import hook?)
  - URL expiry/refresh (regenerate `.strm` on demand?)
