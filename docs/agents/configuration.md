# Configuration

AniBridge centralizes configuration in `app/config.py`. Values are derived from environment variables, `.env`, and defaults.

## Key Groups

- Paths: `DATA_DIR`, `DOWNLOAD_DIR`, `QBIT_PUBLIC_SAVE_PATH`
- Migrations: `DB_MIGRATE_ON_STARTUP`
- Torznab: `INDEXER_NAME`, `INDEXER_API_KEY`, `TORZNAB_*`
- Downloader: `PROVIDER_ORDER`, `MAX_CONCURRENCY`, `DOWNLOADS_TTL_HOURS`, `CLEANUP_SCAN_INTERVAL_MIN`
- Proxy: `PROXY_*`, protocol overrides, certificate toggles, IP monitoring
- Provider order default: `VOE,Filemoon,Streamtape,Vidmoly,SpeedFiles,Doodstream,LoadX,Luluvdo,Vidoza`
- Update notifier: `ANIBRIDGE_UPDATE_CHECK`, GitHub owner/repo/token, GHCR image reference
- Logging: `LOG_LEVEL`, progress toggles

## Environment Variable Catalog

1. `LOG_LEVEL` — Loguru logging level (default `INFO`).
2. `DATA_DIR` — Root data directory (default `./data`).
3. `DOWNLOAD_DIR` — Download location (default `${DATA_DIR}/downloads/anime`).
4. `QBIT_PUBLIC_SAVE_PATH` — Public path seen by qBittorrent clients (default empty).
5. `DB_MIGRATE_ON_STARTUP` — Run Alembic migrations on startup (default `true`).
6. `ANIBRIDGE_RELOAD` — Enable reload server mode (`false` by default).
7. `PUID` — UID for container user (default `1000`).
8. `PGID` — GID for container group (default `1000`).
9. `CHOWN_RECURSIVE` — Entrypoint recursive chown (`true`).
10. `ANIWORLD_ALPHABET_HTML` — Override local HTML (default empty, triggers remote fetch).
11. `ANIWORLD_ALPHABET_URL` — AniWorld alphabet page (default `https://aniworld.to/animes-alphabet`).
12. `ANIWORLD_TITLES_REFRESH_HOURS` — Title refresh interval (default `24`).
13. `SOURCE_TAG` — Release source tag (default `WEB`).
14. `RELEASE_GROUP` — Release group label (default `aniworld`).
15. `PROVIDER_ORDER` — Comma-separated provider priority list.
16. `MAX_CONCURRENCY` — Thread pool size (default `3`).
17. `INDEXER_NAME` — Torznab display name (default `AniBridge Torznab`).
18. `INDEXER_API_KEY` — Optional Torznab API key.
19. `TORZNAB_CAT_ANIME` — Category mapping (default `5070`).
20. `AVAILABILITY_TTL_HOURS` — Availability cache TTL (default `24`).
21. `TORZNAB_FAKE_SEEDERS` — Seeders in results (default `999`).
22. `TORZNAB_FAKE_LEECHERS` — Leechers in results (default `787`).
23. `TORZNAB_RETURN_TEST_RESULT` — Return test item (default `true`).
24. `TORZNAB_TEST_TITLE` — Test item title.
25. `TORZNAB_TEST_SLUG` — Test item slug.
26. `TORZNAB_TEST_SEASON` — Test season number.
27. `TORZNAB_TEST_EPISODE` — Test episode number.
28. `TORZNAB_TEST_LANGUAGE` — Test language label.
29. `DELETE_FILES_ON_TORRENT_DELETE` — Remove files on delete (default `true`).
30. `DOWNLOADS_TTL_HOURS` — TTL cleanup threshold (default `0`, disabled).
31. `CLEANUP_SCAN_INTERVAL_MIN` — Cleanup interval (default `30`).
32. `STRM_FILES_MODE` — STRM mode (`no`, `both`, `only`, default `no`).
33. `STRM_PROXY_MODE` — STRM proxy mode (`direct`, `proxy`, `redirect`, default `proxy`).
34. `STRM_PUBLIC_BASE_URL` — Public base URL for STRM proxy URLs.
35. `STRM_PROXY_AUTH` — STRM proxy auth mode (`none`, `token`, `apikey`).
36. `STRM_PROXY_SECRET` — Shared secret for STRM proxy auth (required when auth is not `none`).
37. `STRM_PROXY_CACHE_TTL_SECONDS` — STRM URL cache TTL in seconds (default `0`).
38. `PROGRESS_FORCE_BAR` — Force progress bar (default `false`).
39. `PROGRESS_STEP_PERCENT` — Progress logging step (default `5`).
40. `ANIBRIDGE_UPDATE_CHECK` — Enable release polling (default `true`).
41. `ANIBRIDGE_GITHUB_TOKEN` — GitHub API token.
42. `ANIBRIDGE_GITHUB_OWNER` — GitHub owner (default `zzackllack`).
43. `ANIBRIDGE_GITHUB_REPO` — Repo name (default `AniBridge`).
44. `ANIBRIDGE_GHCR_IMAGE` — GHCR image slug (default `zzackllack/anibridge`).
45. `PROXY_ENABLED` — Enable proxy (default `false`).
46. `PROXY_URL` — Full proxy URL with optional credentials.
47. `PROXY_HOST` — Proxy host when building URL from parts.
48. `PROXY_PORT` — Proxy port.
49. `PROXY_SCHEME` — Proxy scheme (default `socks5`).
50. `PROXY_USERNAME` — Proxy auth username.
51. `PROXY_PASSWORD` — Proxy auth password.
52. `HTTP_PROXY_URL` — Protocol-specific override.
53. `HTTPS_PROXY_URL` — Protocol-specific override.
54. `ALL_PROXY_URL` — Generic override for all protocols.
55. `NO_PROXY` — Domains bypassing proxy.
56. `PROXY_FORCE_REMOTE_DNS` — Force remote DNS for SOCKS proxies (default `true`).
57. `PROXY_DISABLE_CERT_VERIFY` — Disable TLS verification (default `false`).
58. `PROXY_APPLY_ENV` — Apply proxies to process env (default `true`).
59. `PROXY_IP_CHECK_INTERVAL_MIN` — IP check interval minutes (default `30`).
60. `PROXY_SCOPE` — Scope of proxy usage (`all`, `requests`, `ytdlp`).
61. `PUBLIC_IP_CHECK_ENABLED` — Run IP monitor even when proxy disabled (default `false`).
62. `PUBLIC_IP_CHECK_INTERVAL_MIN` — Override for IP check interval (defaults to proxy interval).
63. `PYTHONUNBUFFERED` — Set to `1` in Docker to keep logs flush.
64. `ANIBRIDGE_DOCS_BASE_URL` — Docs base URL (if introduced).
65. `QBIT_PUBLIC_SAVE_PATH` — Mapped path for completed downloads.
66. `SONARR_*`, `PROWLARR_*` — Integration values documented in `docs/src/integrations`.
