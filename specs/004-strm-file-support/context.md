# context.md — AniBridge STRM support (Torznab + Jellyfin/Emby/Kodi)

## Goal (what we are building)

Add an optional “STRM mode” to AniBridge so that, instead of downloading the actual media file onto the AniBridge/Sonarr host, the pipeline can produce a **.strm** file that points to a **remote, internet-reachable URL** for the media. Media servers (Jellyfin/Emby/Kodi/etc.) can then index the `.strm` file and play the remote stream.

This must be controlled by a new ENV var with values:

- `no` (default): behave exactly like today; no behavior changes.
- `both`: expose BOTH variants for each result: (1) current download-via-yt-dlp, (2) STRM variant.
- `only`: expose ONLY the STRM variant.

## What a .strm file is (key constraints)

- A `.strm` file is typically a **plain text file** that contains a **single line** with a **path or URL** to streamable media content.
- For our use-case we will write **one HTTPS URL per file** (UTF-8, newline at end).
- The URL should point to a media resource that the playback stack can open (e.g. direct `.mp4`, `.mkv`, or an endpoint that serves the media bytes).

### Playback / networking reality check

Different players handle `.strm` differently:

- Some clients (e.g., Kodi-like flows) may try to resolve/play the URL **directly on the client**.
- Some server-based stacks may fetch/relay the URL **via the media server**.
So the URL must be reachable from **wherever playback is executed** (server and/or clients depending on the setup). Avoid private RFC1918-only URLs unless you know all clients can reach them.

### Seeking/scrubbing & metadata

For a good experience, the remote server should ideally support:

- `Accept-Ranges` / HTTP range requests (for seeking),
- `Content-Length` (duration/seek bar/“0 length” issues are common when not available),
- stable URL (avoid short-lived tokens unless you implement refresh logic).

## Jellyfin/Emby indexing gotchas (naming and scanning)

- Jellyfin libraries can ignore certain “sample”/extra-like names depending on naming rules / reserved keywords.
- When generating `.strm` filenames, avoid including `"sample"` in the basename.
- Keep filenames consistent with your library naming scheme (Show/Season/Episode), because media servers match metadata largely based on file path conventions.

## Sonarr / Prowlarr / Torznab implications (important!)

AniBridge is acting as a **Torznab indexer**. Sonarr/Radarr discover releases via the Torznab RSS/search feed and then pass a chosen release to a **download client** (qBittorrent, etc.) by downloading the enclosure URL or magnet.

That means:

- “Returning a .strm” to Sonarr typically does NOT mean Sonarr will magically stream it; it still expects a downloadable artifact from the indexer.
- The practical approach is: for the STRM variant, AniBridge should provide a **downloadable artifact** (usually via HTTP) that results in a `.strm` file landing in the right place.
  - Option A: the Torznab entry’s download URL returns a small file that the download client saves as `.strm` (simple).
  - Option B: keep using the existing “fake torrent / shim pipeline” (if AniBridge already does that for yt-dlp) but have the STRM variant trigger “create `.strm` file” instead of “download media”.
- If `both`, you must ensure the two variants are distinguishable:
  - unique GUID/infoHash/ID,
  - distinct title suffix/prefix, e.g. `[STRM]`,
  - maybe slightly different “size” fields (STRM is tiny) so Sonarr’s quality sorting doesn’t accidentally prefer it unless intended.

### Compatibility warning (real-world)

Not every Arr component treats `.strm` as a normal media file:

- Some users report `.strm` works in certain workflows, but other tools (e.g., subtitle managers) may not parse `.strm`.
- Radarr/Sonarr behavior can differ by version and configuration.
Therefore: build this feature so it’s **opt-in**, default `no`, and easy to roll back.

## AniBridge repo context (where changes likely go)

In this repository, STRM support will likely touch:

- Torznab API layer: where search results are converted into Torznab items and enclosure URLs.
- The “download/shim” pipeline that currently enables “torrent-like” results to trigger `yt-dlp`.
- Central config: where env vars are defined/validated and exposed to code.
- Documentation: environment docs, `.env.example`, `docker-compose.yaml`.

Implementation expectations:

- Add one new env var (string enum): e.g. `STRM_FILES_MODE` with `no|both|only` (default `no`).
- Add a small, well-contained helper module for STRM generation:
  - `build_strm_content(url) -> str` and `safe_strm_filename(metadata) -> str`
  - ensure newline and encoding
  - avoid reserved words like `sample`
- Extend Torznab item generation:
  - In `no`: unchanged output.
  - In `only`: emit only STRM items.
  - In `both`: emit two items per logical media result (download + STRM).
- Ensure the STRM item’s download path triggers creation/serving of a `.strm` file (not the real media).
- Update docs + docker-compose + .env.example consistent with existing schema and naming conventions.

## Suggested naming / UX for dual items

- Title: append `[STRM]` to the STRM variant and keep the non-STRM title unchanged.
- Download URL: different endpoint or query flag, e.g. `...?mode=strm`.
- GUID: include mode in the ID to avoid collisions (important for caching).

## Security & correctness checklist

- Never embed internal-only URLs unless your clients can reach them.
- If you generate signed URLs (tokenized), define refresh strategy or accept that old `.strm` becomes dead.
- Sanitize paths: no directory traversal; strict filename policy.
- Log clearly which mode is active and which variant is produced.
- Keep default `no` to avoid surprising behavior changes for existing users.

## “context7” instruction for Codex

When implementing, use context7 to look up:

- Torznab spec expectations / RSS item fields (title, guid, enclosure, attributes),
- any libraries used for settings/env validation,
- HTTP streaming/range handling if AniBridge exposes a proxy/stream endpoint.

End of context.
