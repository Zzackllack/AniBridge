# Configuration

AniBridge centralizes configuration in `apps/api/app/config.py`. Values are derived from environment variables, `.env`, and defaults.

## Key Groups

- Paths: `DATA_DIR`, `DOWNLOAD_DIR`, `QBIT_PUBLIC_SAVE_PATH`
- Migrations: `DB_MIGRATE_ON_STARTUP`
- Torznab: `INDEXER_NAME`, `INDEXER_API_KEY`, `TORZNAB_*`
- Downloader: `PROVIDER_ORDER` (input env var, mapped at runtime to `VIDEO_HOST_ORDER`), `PROVIDER_REDIRECT_TIMEOUT_SECONDS`,
  `PROVIDER_REDIRECT_RETRIES`, `PROVIDER_CHALLENGE_BACKOFF_SECONDS`,
  `MAX_CONCURRENCY`, `DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC`,
  `DOWNLOADS_TTL_HOURS`, `CLEANUP_SCAN_INTERVAL_MIN`
- Provider catalog index: `PROVIDER_INDEX_*` refresh cadence, queue bounds,
  writer batching, and failure-threshold controls for staged catalog refreshes
- STRM: `STRM_FILES_MODE`, `STRM_PROXY_*`
- Networking policy: external VPN/VPN-sidecar routing only + `PUBLIC_IP_CHECK_*`
- Video-host order default: `VOE,Filemoon,Streamtape,Vidmoly,Doodstream,LoadX,Luluvdo,Vidoza` via `PROVIDER_ORDER`, mapped at runtime to `VIDEO_HOST_ORDER`
- s.to/VOE note: if Sonarr shows `qBittorrent is reporting an error` for items
  that never started downloading, inspect logs for provider redirect timeouts and
  tune `PROVIDER_REDIRECT_TIMEOUT_SECONDS` / `PROVIDER_REDIRECT_RETRIES`
  before changing download-layer settings.
- s.to/Turnstile note: Serienstream can now return a Turnstile page for
  `/r?t=...` redirect tokens. AniBridge now retries those pages with browser-like
  navigation headers and a cool-down controlled by
  `PROVIDER_CHALLENGE_BACKOFF_SECONDS`.
- Update notifier: `ANIBRIDGE_UPDATE_CHECK`, GitHub owner/repo/token, GHCR image reference
- Logging: `LOG_LEVEL`, progress toggles

## Environment Variable Catalog

1. `LOG_LEVEL` — Loguru logging level (default `INFO`).
2. `DATA_DIR` — Root data directory (default `./data`).
3. `DOWNLOAD_DIR` — Download location.
4. `QBIT_PUBLIC_SAVE_PATH` — Public path seen by qBittorrent clients (default empty).
5. `DB_MIGRATE_ON_STARTUP` — Run Alembic migrations on startup (default `true`).
6. `ANIBRIDGE_RELOAD` — Enable reload server mode (`false` by default).
7. `PUID` — UID for container user (default `1000`).
8. `PGID` — GID for container group (default `1000`).
9. `CHOWN_RECURSIVE` — Entrypoint recursive chown (`true`).
10. `ANIWORLD_ALPHABET_HTML` — Override local HTML (default empty, triggers remote fetch).
11. `ANIWORLD_ALPHABET_URL` — AniWorld alphabet page (default `https://aniworld.to/animes-alphabet`).
12. `ANIWORLD_TITLES_REFRESH_HOURS` — Title refresh interval (default `24`).
13. `STO_ALPHABET_HTML` — Override local s.to HTML.
14. `STO_ALPHABET_URL` — s.to alphabet page.
15. `STO_TITLES_REFRESH_HOURS` — Title refresh interval for s.to (default `24`).
16. `MEGAKINO_BASE_URL` — Megakino base URL override.
17. `MEGAKINO_TITLES_REFRESH_HOURS` — Megakino refresh interval.
18. `MEGAKINO_DOMAIN_CHECK_INTERVAL_MIN` — Megakino domain checker interval.
19. `CATALOG_SITES` — Enabled catalogue sites.
20. `PROVIDER_INDEX_REFRESH_HOURS` — Default staged provider-index refresh cadence (default `24`).
21. `PROVIDER_INDEX_REFRESH_HOURS_ANIWORLD` — AniWorld provider-index cadence override.
22. `PROVIDER_INDEX_REFRESH_HOURS_STO` — s.to provider-index cadence override.
23. `PROVIDER_INDEX_REFRESH_HOURS_MEGAKINO` — megakino provider-index cadence override.
24. `PROVIDER_INDEX_SCHEDULER_POLL_SECONDS` — Scheduler poll interval for due refreshes (default `60`).
25. `PROVIDER_INDEX_GLOBAL_CONCURRENCY` — Max concurrent provider refreshes (default `1`).
26. `PROVIDER_INDEX_CONCURRENCY_ANIWORLD` — AniWorld title crawl worker count.
27. `PROVIDER_INDEX_CONCURRENCY_STO` — s.to title crawl worker count.
28. `PROVIDER_INDEX_CONCURRENCY_MEGAKINO` — megakino crawl worker count.
29. `PROVIDER_INDEX_TITLE_TIMEOUT_SECONDS` — Soft title crawl timeout threshold (default `45`).
30. `PROVIDER_INDEX_QUEUE_SIZE` — Bounded title-result queue depth between crawlers and the SQLite writer (default `32`).
31. `PROVIDER_INDEX_WRITER_BATCH_SIZE` — SQLite writer commit batch size (default `8`).
32. `PROVIDER_INDEX_WRITER_FLUSH_SECONDS` — Max wait before the writer flushes a partial batch (default `1.0`).
33. `PROVIDER_INDEX_FAILURE_THRESHOLD_PERCENT` — Refresh abort threshold for failed title crawls (default `20`).
34. `PROVIDER_INDEX_BACKPRESSURE_LOG_SECONDS` — Minimum interval between repeated queue-backpressure logs (default `15`).
35. `SOURCE_TAG` — Release source tag (default `WEB`).
36. `RELEASE_GROUP` — Release group label (default `aniworld`).
37. `RELEASE_GROUP_ANIWORLD` — AniWorld release group override.
38. `RELEASE_GROUP_STO` — s.to release group override.
39. `PROVIDER_ORDER` — Comma-separated video-host priority input; mapped at runtime to `VIDEO_HOST_ORDER`.
40. `PROVIDER_REDIRECT_TIMEOUT_SECONDS` — Timeout for resolving catalogue redirect tokens into video-host URLs (default `12`).
41. `PROVIDER_REDIRECT_RETRIES` — Extra retry attempts for transient video-host redirect failures (default `2`).
42. `PROVIDER_CHALLENGE_BACKOFF_SECONDS` — Base cool-down for Turnstile challenge retries (default `300`).
43. `MAX_CONCURRENCY` — Thread pool size (default `3`).
44. `DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC` — Per-download yt-dlp rate cap (`0` disables).
45. `INDEXER_NAME` — Torznab display name (default `AniBridge Torznab`).
46. `INDEXER_API_KEY` — Optional Torznab API key.
47. `TORZNAB_CAT_ANIME` — Category mapping (default `5070`).
48. `TORZNAB_CAT_MOVIE` — Movie category mapping (default `2000`).
49. `AVAILABILITY_TTL_HOURS` — Availability cache TTL (default `24`).
50. `TORZNAB_FAKE_SEEDERS` — Seeders in results (default `999`).
51. `TORZNAB_FAKE_LEECHERS` — Leechers in results (default `787`).
52. `TORZNAB_RETURN_TEST_RESULT` — Return test item (default `true`).
53. `TORZNAB_TEST_TITLE` — Test item title.
54. `TORZNAB_TEST_SLUG` — Test item slug.
55. `TORZNAB_TEST_SEASON` — Test season number.
56. `TORZNAB_TEST_EPISODE` — Test episode number.
57. `TORZNAB_TEST_LANGUAGE` — Test language label.
58. `TORZNAB_SEASON_SEARCH_MODE` — Season-search execution mode (`fast`/`strict`, default `fast`).
59. `TORZNAB_SEASON_SEARCH_MAX_EPISODES` — Season-search fallback probe ceiling (default `60`).
60. `TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES` — Season-search fallback stop threshold (default `3`).
61. `DELETE_FILES_ON_TORRENT_DELETE` — Remove files on delete (default `true`).
62. `DOWNLOADS_TTL_HOURS` — TTL cleanup threshold (default `0`, disabled).
63. `CLEANUP_SCAN_INTERVAL_MIN` — Cleanup interval (default `30`).
64. `STRM_FILES_MODE` — STRM mode (`no`, `both`, `only`, default `no`).
65. `STRM_PROXY_MODE` — STRM proxy mode (`direct`, `proxy`, `redirect`, default `direct`).
66. `STRM_PUBLIC_BASE_URL` — Public base URL for STRM proxy URLs.
67. `STRM_PROXY_AUTH` — STRM proxy auth mode (`none`, `token`, `apikey`).
68. `STRM_PROXY_SECRET` — Shared secret for STRM proxy auth.
69. `STRM_PROXY_UPSTREAM_ALLOWLIST` — Comma-separated upstream host allowlist.
70. `STRM_PROXY_CACHE_TTL_SECONDS` — STRM URL cache TTL in seconds (default `0`).
71. `STRM_PROXY_TOKEN_TTL_SECONDS` — STRM proxy token TTL in seconds (default `900`).
72. `PROGRESS_FORCE_BAR` — Force progress bar (default `false`).
73. `PROGRESS_STEP_PERCENT` — Progress logging step (default `5`).
74. `ANIBRIDGE_UPDATE_CHECK` — Enable release polling (default `true`).
75. `ANIBRIDGE_GITHUB_TOKEN` — GitHub API token.
76. `ANIBRIDGE_GITHUB_OWNER` — GitHub owner (default `zzackllack`).
77. `ANIBRIDGE_GITHUB_REPO` — Repo name (default `AniBridge`).
78. `ANIBRIDGE_GHCR_IMAGE` — GHCR image slug (default `zzackllack/anibridge`).
79. `PUBLIC_IP_CHECK_ENABLED` — Enable periodic public IP logging (default `false`).
80. `PUBLIC_IP_CHECK_INTERVAL_MIN` — Public IP check interval minutes (default `30`).
81. `ANIBRIDGE_HOST` — Bind host.
82. `ANIBRIDGE_PORT` — Bind port.
83. `ANIBRIDGE_CORS_ORIGINS` — CORS origins.
84. `ANIBRIDGE_CORS_ALLOW_CREDENTIALS` — CORS credentials behavior.
85. `ANIBRIDGE_TEST_MODE` — Test-mode runtime toggle.
86. `PYTHONUNBUFFERED` — Set to `1` in Docker to keep logs flush.
87. `SONARR_*`, `PROWLARR_*` — Integration values documented in `docs/src/integrations/clients`.

## Removed Legacy Proxy Variables

The in-app outbound proxy feature was removed. These settings are intentionally
unsupported and ignored if still present in runtime env:

- `PROXY_ENABLED`, `PROXY_URL`, `HTTP_PROXY_URL`, `HTTPS_PROXY_URL`, `ALL_PROXY_URL`
- `PROXY_HOST`, `PROXY_PORT`, `PROXY_SCHEME`, `PROXY_USERNAME`, `PROXY_PASSWORD`
- `NO_PROXY`, `PROXY_FORCE_REMOTE_DNS`, `PROXY_DISABLE_CERT_VERIFY`, `PROXY_APPLY_ENV`
- `PROXY_IP_CHECK_INTERVAL_MIN`, `PROXY_SCOPE`
