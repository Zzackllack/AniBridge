---
title: Troubleshooting
outline: deep
---

# Troubleshooting

## Torznab shows no results

- Confirm `t`, `q`, `season`, and `ep` parameters for `/torznab/api`
- Try `t=search` with empty `q` to get the connectivity test item when `TORZNAB_RETURN_TEST_RESULT=true`
- Ensure `INDEXER_API_KEY` is provided as `apikey` if configured
- Inspect `data/terminal-*.log` for parsing/probe errors

## Sonarr cannot connect to qBittorrent

- Base URL should be `http://host:8000/` and type “qBittorrent”
- Authentication is stubbed; any username/password works
- Categories are available via `/api/v2/torrents/categories`

## Downloads fail immediately

- Check `PROVIDER_ORDER` and language availability
- Validate ffmpeg/ffprobe in PATH for proper renaming
- Inspect `app/core/downloader.py` logs for provider exceptions

## Wrong save path reported to Sonarr

- Symptom: Sonarr error “You are using Docker; download client places downloads in `<host path>` but this directory does not appear to exist inside the container.”
- Set `QBIT_PUBLIC_SAVE_PATH` to the path Sonarr sees (e.g., `/downloads`).
- Mount the same host folder into both containers (`-v /host/downloads:/downloads` for Sonarr; `-v /host/downloads:/data/downloads` for AniBridge).
- Verify via `GET /api/v2/app/preferences` that `save_path` is `/downloads`.

## Progress bar looks odd or spams the log

- If you see digits like `##6` instead of a bar, your terminal is in ASCII mode. AniBridge forces Unicode bars; if your terminal can’t display Unicode, consider `PROGRESS_FORCE_BAR=false` to get stepped logging only.
- If your `data/terminal-*.log` fills with progress lines, ensure you’re running the latest build: AniBridge routes tqdm output directly to the real terminal to keep logs clean. Non‑TTY runs log one line every `PROGRESS_STEP_PERCENT` (default 5%).
- No bar showing? Set `PROGRESS_FORCE_BAR=true` when running under a reloader or when stdout isn’t a TTY.

## DOWNLOAD_DIR not writable

- Symptom: `PermissionError` or read‑only warnings in logs.
- Fix: Point `DOWNLOAD_DIR` to a writable path or correct volume mounts. The app will exit early if it cannot create the directory.

## Stale title resolution

- Adjust `ANIWORLD_TITLES_REFRESH_HOURS`
- Provide a snapshot via `ANIWORLD_ALPHABET_HTML` if network restricted

## Megakino domain resolution fails

- Check logs for "megakino domain" or "mirrors" entries at startup.
- Override with `MEGAKINO_BASE_URL` if automatic resolution fails.
- Set `MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN=0` to disable background checks during troubleshooting.
- Remember megakino is search-only; queries must provide a slug or a megakino URL containing one.

## Sonarr fails to import completed downloads due to "No audio tracks detected"

> [!WARNING]
> This is a known Sonarr behavior with `.strm` files. When Sonarr's
> ffprobe succeeds on a `.strm`, it may report zero audio tracks and
> reject the import. This is not an AniBridge issue. Workarounds: manual
> import or disable "Analyze video files" in Sonarr. For details, see
> [Issue #50](https://github.com/Zzackllack/AniBridge/issues/50).

## Sonarr import error: "Invalid season or episode"

- Symptom: Sonarr grabs a release like `S00E05` but import fails with
  `Invalid season or episode`.
- Check AniBridge-reported `content_path` via
  `GET /api/v2/torrents/info`; it must contain the same `SxxEyy`
  token as the grabbed release title.
- Ensure you are running a version that preserves alias numbering in
  final rename for specials/extras mappings. Older builds could return
  mismatched `content_path` numbering and fail import validation.

## STRM proxy playback shows "Video-Bitrate: 0 kbps" in Jellyfin

> [!WARNING]
> This is a known limitation for some STRM proxy + HLS playback paths in
> Jellyfin and similar players. AniBridge has no reliable near-term fix that
> avoids playback regressions (timeline/duration mismatch, early playback stop,
> next-episode auto-jump). If you hit this, prefer direct mode or a
> client/server-specific workaround. For details, see
> [Issue #51](https://github.com/Zzackllack/anibridge/issues/51).

## Direct Play fails or forces transcoding in browser clients

- Ensure AniBridge is reachable over HTTPS when Jellyfin/Plex/Emby is HTTPS.
- Mixed content blocking will prevent browsers from loading HTTP streams on an HTTPS page.
- Put AniBridge behind a reverse proxy with TLS and set `STRM_PUBLIC_BASE_URL` to the HTTPS URL.
- If clients cannot reach AniBridge at the public URL, Direct Play cannot work even over HTTPS.
  Expose AniBridge publicly (or to your LAN) and ensure the URL is reachable by both the
  media server and the client device.
- Check the browser devtools console for mixed content errors.
- Even when Direct Play fails, the fallback is often a lightweight stream copy/proxy
  rather than a full re-encode. A modern CPU (or GPU) typically handles this fine,
  but it still consumes server resources and can affect multiple concurrent streams.
