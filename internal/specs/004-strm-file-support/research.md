# STRM File Support — Research Notes

## Problem recap

AniBridge currently behaves like a Torznab indexer + qBittorrent “shim”:

1. Prowlarr/Sonarr query `/torznab/api` and receive RSS items with **magnet** enclosures.
2. Sonarr sends the chosen magnet to AniBridge’s qBittorrent shim (`/api/v2/torrents/add`).
3. AniBridge schedules a job that resolves a provider link and downloads media via `yt-dlp`.

The goal of “STRM support” is to allow an alternative outcome where the “downloaded artifact” is a **`.strm` file** (not the media bytes), suitable for Jellyfin/Emby/Kodi-style playback.

## What a `.strm` file is (format constraints)

In the common media-server ecosystem, `.strm` is:

- Plain text
- Typically **one line**
- Containing either a **filesystem path** or a **URL**
- Recommended to be newline-terminated and encoded as UTF-8

For AniBridge, the intended shape is:

- Exactly one **HTTP(S) URL** per `.strm` file

## Arr ecosystem implications (Torznab + download client reality)

Arr apps do not “stream” directly from Torznab search results. They:

- Treat the indexer as a discovery source
- Select a release
- Hand it off to a **download client**

So “returning a STRM” to Sonarr/Prowlarr means:

- The Torznab item must still behave like a downloadable release (magnet/enclosure)
- The chosen item must result in a **file landing in the download client’s output location**

In AniBridge, the simplest compatible implementation is:

- Keep magnets as the transport
- Add a **variant flag in the magnet payload**
- Have the shim schedule a “create `.strm` file” job instead of “download media”

## Approaches considered

### A) `.strm` contains *provider direct URL* (implemented)

AniBridge resolves a provider “direct link” (the same link used for `yt-dlp`) and writes it into `.strm`.

Pros:

- Minimal code; no new streaming/proxy endpoints required.
- Works even if the Jellyfin server cannot reach the AniBridge host storage.

Cons:

- Provider URLs may be **tokenized/short-lived**, causing stale `.strm`.
- Playback may fail if the player expects certain HTTP features (range support, stable content-length).

### B) `.strm` contains an AniBridge “proxy stream” URL (not implemented)

`.strm` would point to an AniBridge endpoint that resolves the provider and streams bytes (ideally supporting range requests).

Pros:

- Stable URL surface for media servers; AniBridge can refresh underlying provider URLs.
- Central place to implement retries/auth/cookies.

Cons:

- Much more complex (range requests, caching, performance, legal risk).
- Increases bandwidth requirements on the AniBridge host.

### C) `.strm` contains a URL to a remote file you host (not implemented)

Requires a way to construct a remote URL for a file you’ve already stored elsewhere.

Pros:

- Predictable/stable URLs.
- Offloads playback bandwidth to your file host.

Cons:

- Requires additional infrastructure and additional configuration in AniBridge (URL templating, authentication, etc.).

## Chosen contract (what is implemented)

- New env var `STRM_FILES_MODE` with values:
  - `no` (default): current behavior unchanged.
  - `both`: Torznab returns **two** items per release (download + STRM).
  - `only`: Torznab returns only STRM items.
- STRM items:
  - Have a visible title suffix ` [STRM]`
  - Carry a distinct magnet infohash and an embedded `{prefix}_mode=strm` field
- When the qBittorrent shim receives a magnet with `{prefix}_mode=strm`:
  - AniBridge schedules a “STRM job” that:
    - resolves a direct provider URL via the AniWorld lib
    - writes a `.strm` file containing that URL (UTF-8, newline at end)
    - completes the job with `result_path` pointing to the `.strm`

## Operational caveats

- **URL stability:** If the provider link expires, existing `.strm` files will stop working.
- **Playback origin:** Depending on the client/player, the URL may be fetched by the media server or by the client device.
- **Sonarr import behavior:** Whether Sonarr imports `.strm` into the series folder depends on Sonarr version and settings; workflows may need adjustment.

## Security considerations

- `.strm` content is treated as a URL; avoid writing internal/private URLs unless you understand the network topology.
- Ensure `.strm` filenames are sanitized (no traversal, no invalid characters).

