# Configuration

AniBridge centralizes configuration in `app/config.py`. Values are derived from environment variables, `.env`, and defaults.

## Key Groups

- Paths: `DATA_DIR`, `DOWNLOAD_DIR`, `QBIT_PUBLIC_SAVE_PATH`
- Migrations: `DB_MIGRATE_ON_STARTUP`
- Torznab: `INDEXER_NAME`, `INDEXER_API_KEY`, `TORZNAB_*`
- Downloader: `PROVIDER_ORDER`, `PROVIDER_REDIRECT_TIMEOUT_SECONDS`, `PROVIDER_REDIRECT_RETRIES`, `MAX_CONCURRENCY`, `DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC`, `DOWNLOADS_TTL_HOURS`, `CLEANUP_SCAN_INTERVAL_MIN`
- STRM: `STRM_FILES_MODE`, `STRM_PROXY_*`
- Networking policy: external VPN/VPN-sidecar routing only + `PUBLIC_IP_CHECK_*`
- Provider order default: `VOE,Filemoon,Streamtape,Vidmoly,Doodstream,LoadX,Luluvdo,Vidoza`
- s.to/VOE note: if Sonarr shows `qBittorrent is reporting an error` for items
  that never started downloading, inspect logs for provider redirect timeouts and
  tune `PROVIDER_REDIRECT_TIMEOUT_SECONDS` / `PROVIDER_REDIRECT_RETRIES`
  before changing download-layer settings.
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
20. `SOURCE_TAG` — Release source tag (default `WEB`).
21. `RELEASE_GROUP` — Release group label (default `aniworld`).
22. `RELEASE_GROUP_ANIWORLD` — AniWorld release group override.
23. `RELEASE_GROUP_STO` — s.to release group override.
24. `PROVIDER_ORDER` — Comma-separated provider priority list.
25. `PROVIDER_REDIRECT_TIMEOUT_SECONDS` — Timeout for resolving catalogue redirect tokens into provider URLs (default `12`).
26. `PROVIDER_REDIRECT_RETRIES` — Extra retry attempts for transient provider redirect failures (default `2`).
27. `MAX_CONCURRENCY` — Thread pool size (default `3`).
28. `DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC` — Per-download yt-dlp rate cap (`0` disables).
29. `INDEXER_NAME` — Torznab display name (default `AniBridge Torznab`).
30. `INDEXER_API_KEY` — Optional Torznab API key.
31. `TORZNAB_CAT_ANIME` — Category mapping (default `5070`).
32. `TORZNAB_CAT_MOVIE` — Movie category mapping (default `2000`).
33. `AVAILABILITY_TTL_HOURS` — Availability cache TTL (default `24`).
34. `TORZNAB_FAKE_SEEDERS` — Seeders in results (default `999`).
35. `TORZNAB_FAKE_LEECHERS` — Leechers in results (default `787`).
36. `TORZNAB_RETURN_TEST_RESULT` — Return test item (default `true`).
37. `TORZNAB_TEST_TITLE` — Test item title.
38. `TORZNAB_TEST_SLUG` — Test item slug.
39. `TORZNAB_TEST_SEASON` — Test season number.
40. `TORZNAB_TEST_EPISODE` — Test episode number.
41. `TORZNAB_TEST_LANGUAGE` — Test language label.
42. `TORZNAB_SEASON_SEARCH_MODE` — Season-search execution mode (`fast`/`strict`, default `fast`).
43. `TORZNAB_SEASON_SEARCH_MAX_EPISODES` — Season-search fallback probe ceiling (default `60`).
44. `TORZNAB_SEASON_SEARCH_MAX_CONSECUTIVE_MISSES` — Season-search fallback stop threshold (default `3`).
45. `DELETE_FILES_ON_TORRENT_DELETE` — Remove files on delete (default `true`).
46. `DOWNLOADS_TTL_HOURS` — TTL cleanup threshold (default `0`, disabled).
47. `CLEANUP_SCAN_INTERVAL_MIN` — Cleanup interval (default `30`).
48. `STRM_FILES_MODE` — STRM mode (`no`, `both`, `only`, default `no`).
49. `STRM_PROXY_MODE` — STRM proxy mode (`direct`, `proxy`, `redirect`, default `direct`).
50. `STRM_PUBLIC_BASE_URL` — Public base URL for STRM proxy URLs.
51. `STRM_PROXY_AUTH` — STRM proxy auth mode (`none`, `token`, `apikey`).
52. `STRM_PROXY_SECRET` — Shared secret for STRM proxy auth.
53. `STRM_PROXY_UPSTREAM_ALLOWLIST` — Comma-separated upstream host allowlist.
54. `STRM_PROXY_CACHE_TTL_SECONDS` — STRM URL cache TTL in seconds (default `0`).
55. `STRM_PROXY_TOKEN_TTL_SECONDS` — STRM proxy token TTL in seconds (default `900`).
56. `PROGRESS_FORCE_BAR` — Force progress bar (default `false`).
57. `PROGRESS_STEP_PERCENT` — Progress logging step (default `5`).
58. `ANIBRIDGE_UPDATE_CHECK` — Enable release polling (default `true`).
59. `ANIBRIDGE_GITHUB_TOKEN` — GitHub API token.
60. `ANIBRIDGE_GITHUB_OWNER` — GitHub owner (default `zzackllack`).
61. `ANIBRIDGE_GITHUB_REPO` — Repo name (default `AniBridge`).
62. `ANIBRIDGE_GHCR_IMAGE` — GHCR image slug (default `zzackllack/anibridge`).
63. `PUBLIC_IP_CHECK_ENABLED` — Enable periodic public IP logging (default `false`).
64. `PUBLIC_IP_CHECK_INTERVAL_MIN` — Public IP check interval minutes (default `30`).
65. `ANIBRIDGE_HOST` — Bind host.
66. `ANIBRIDGE_PORT` — Bind port.
67. `ANIBRIDGE_CORS_ORIGINS` — CORS origins.
68. `ANIBRIDGE_CORS_ALLOW_CREDENTIALS` — CORS credentials behavior.
69. `ANIBRIDGE_TEST_MODE` — Test-mode runtime toggle.
70. `PYTHONUNBUFFERED` — Set to `1` in Docker to keep logs flush.
71. `SONARR_*`, `PROWLARR_*` — Integration values documented in `docs/src/integrations/clients`.

## Removed Legacy Proxy Variables

The in-app outbound proxy feature was removed. These settings are intentionally
unsupported and ignored if still present in runtime env:

- `PROXY_ENABLED`, `PROXY_URL`, `HTTP_PROXY_URL`, `HTTPS_PROXY_URL`, `ALL_PROXY_URL`
- `PROXY_HOST`, `PROXY_PORT`, `PROXY_SCHEME`, `PROXY_USERNAME`, `PROXY_PASSWORD`
- `NO_PROXY`, `PROXY_FORCE_REMOTE_DNS`, `PROXY_DISABLE_CERT_VERIFY`, `PROXY_APPLY_ENV`
- `PROXY_IP_CHECK_INTERVAL_MIN`, `PROXY_SCOPE`
