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
- Mount the same host folder into both containers (`-v /host/downloads:/downloads` for Sonarr; `-v /host/downloads:/data/downloads/anime` for AniBridge).
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
