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

- Set `QBIT_PUBLIC_SAVE_PATH` to the path Sonarr sees (container path mapping)

## Stale title resolution

- Adjust `ANIWORLD_TITLES_REFRESH_HOURS`
- Provide a snapshot via `ANIWORLD_ALPHABET_HTML` if network restricted

