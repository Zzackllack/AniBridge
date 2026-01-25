# Configuration

AniBridge centralizes configuration in `app/config.py`. Values are derived from environment variables, `.env`, and defaults.

## Key Groups

- Paths: `DATA_DIR`, `DOWNLOAD_DIR`, `QBIT_PUBLIC_SAVE_PATH`
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
5. `ANIBRIDGE_RELOAD` — Enable reload server mode (`false` by default).
6. `PUID` — UID for container user (default `1000`).
7. `PGID` — GID for container group (default `1000`).
8. `CHOWN_RECURSIVE` — Entrypoint recursive chown (`true`).
9. `ANIWORLD_ALPHABET_HTML` — Override local HTML (default empty, triggers remote fetch).
10. `ANIWORLD_ALPHABET_URL` — AniWorld alphabet page (default `https://aniworld.to/animes-alphabet`).
11. `ANIWORLD_TITLES_REFRESH_HOURS` — Title refresh interval (default `24`).
12. `SOURCE_TAG` — Release source tag (default `WEB`).
13. `RELEASE_GROUP` — Release group label (default `aniworld`).
14. `PROVIDER_ORDER` — Comma-separated provider priority list.
15. `MAX_CONCURRENCY` — Thread pool size (default `3`).
16. `INDEXER_NAME` — Torznab display name (default `AniBridge Torznab`).
17. `INDEXER_API_KEY` — Optional Torznab API key.
18. `TORZNAB_CAT_ANIME` — Category mapping (default `5070`).
19. `AVAILABILITY_TTL_HOURS` — Availability cache TTL (default `24`).
20. `TORZNAB_FAKE_SEEDERS` — Seeders in results (default `999`).
21. `TORZNAB_FAKE_LEECHERS` — Leechers in results (default `787`).
22. `TORZNAB_RETURN_TEST_RESULT` — Return test item (default `true`).
23. `TORZNAB_TEST_TITLE` — Test item title.
24. `TORZNAB_TEST_SLUG` — Test item slug.
25. `TORZNAB_TEST_SEASON` — Test season number.
26. `TORZNAB_TEST_EPISODE` — Test episode number.
27. `TORZNAB_TEST_LANGUAGE` — Test language label.
28. `DELETE_FILES_ON_TORRENT_DELETE` — Remove files on delete (default `true`).
29. `DOWNLOADS_TTL_HOURS` — TTL cleanup threshold (default `0`, disabled).
30. `CLEANUP_SCAN_INTERVAL_MIN` — Cleanup interval (default `30`).
31. `STRM_FILES_MODE` — STRM mode (`no`, `both`, `only`, default `no`).
32. `PROGRESS_FORCE_BAR` — Force progress bar (default `false`).
33. `PROGRESS_STEP_PERCENT` — Progress logging step (default `5`).
34. `ANIBRIDGE_UPDATE_CHECK` — Enable release polling (default `true`).
35. `ANIBRIDGE_GITHUB_TOKEN` — GitHub API token.
36. `ANIBRIDGE_GITHUB_OWNER` — GitHub owner (default `zzackllack`).
37. `ANIBRIDGE_GITHUB_REPO` — Repo name (default `AniBridge`).
38. `ANIBRIDGE_GHCR_IMAGE` — GHCR image slug (default `zzackllack/anibridge`).
39. `PROXY_ENABLED` — Enable proxy (default `false`).
40. `PROXY_URL` — Full proxy URL with optional credentials.
41. `PROXY_HOST` — Proxy host when building URL from parts.
42. `PROXY_PORT` — Proxy port.
43. `PROXY_SCHEME` — Proxy scheme (default `socks5`).
44. `PROXY_USERNAME` — Proxy auth username.
45. `PROXY_PASSWORD` — Proxy auth password.
46. `HTTP_PROXY_URL` — Protocol-specific override.
47. `HTTPS_PROXY_URL` — Protocol-specific override.
48. `ALL_PROXY_URL` — Generic override for all protocols.
49. `NO_PROXY` — Domains bypassing proxy.
50. `PROXY_FORCE_REMOTE_DNS` — Force remote DNS for SOCKS proxies (default `true`).
51. `PROXY_DISABLE_CERT_VERIFY` — Disable TLS verification (default `false`).
52. `PROXY_APPLY_ENV` — Apply proxies to process env (default `true`).
53. `PROXY_IP_CHECK_INTERVAL_MIN` — IP check interval minutes (default `30`).
54. `PROXY_SCOPE` — Scope of proxy usage (`all`, `requests`, `ytdlp`).
55. `PUBLIC_IP_CHECK_ENABLED` — Run IP monitor even when proxy disabled (default `false`).
56. `PUBLIC_IP_CHECK_INTERVAL_MIN` — Override for IP check interval (defaults to proxy interval).
57. `PYTHONUNBUFFERED` — Set to `1` in Docker to keep logs flush.
58. `ANIBRIDGE_DOCS_BASE_URL` — Docs base URL (if introduced).
59. `QBIT_PUBLIC_SAVE_PATH` — Mapped path for completed downloads.
60. `SONARR_*`, `PROWLARR_*` — Integration values documented in `docs/src/integrations`.
