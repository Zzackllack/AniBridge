# AniBridge

<a href="https://anibridge-docs.zacklack.de" target="_blank" style="float: right;">
  <img src="img/logo.png" width="164" height="164" alt="AniBridge Logo" align="right" />
</a>

AniBridge is a minimal FastAPI service that bridges anime, series, and movie streaming catalogues (AniWorld, Serienstream/s.to, megakino, and optionally Filmo) to automation tools. It exposes a fake Torznab feed and a fake qBittorrent-compatible API so that applications like Prowlarr/Sonarr/Radarr can discover and download releases automatically. Media is downloaded by your local AniBridge instance.

> [!CAUTION]
> ⚖️ Before using this software, please read the  
> [Legal and Compliance overview](https://anibridge-docs.zacklack.de/legal/).

![AniWorld-Badge](./img/aniworld-badge.svg) ![Serienstream-Badge](./img/serienstream-badge.svg) ![Megakino-Badge](./img/megakino-badge.svg)

## Features

- **Torznab endpoint** that indexes available releases from AniWorld, Serienstream (s.to), and megakino, plus optional Filmo movies in catalog query mode.
- **Two search paths:** legacy query-time provider scraping (the default) and opt-in collector-backed catalog query mode. Legacy mode is deprecated but still available; query mode reads previously collected metadata and keeps media downloads local.
- **qBittorrent API shim** allowing Prowlarr/Sonarr/Radarr to enqueue durable local downloads.
- **Background scheduler** with progress tracking, cancellation, and completed-import handoff.
- **STRM files and STRM proxy** support for stable streaming URLs.
- Simple `/health` endpoint for container or orchestration checks.
- Docker Image for easy deployment

> [!NOTE]
> Sonarr can occasionally reject `.strm` imports with “No audio tracks detected” even when playback works in
> Jellyfin. If this happens, use manual import or disable “Analyze video files” in Sonarr. See
> [Issue #50](https://github.com/zzackllack/anibridge/issues/50).

## Current Status

- Stable release images are cut from the default branch and keep legacy search as the default. They do not automatically include the catalog query work.
- Catalog query mode is advanced, operator-configured preview functionality. It requires a collector you run or otherwise control. There is no hosted, token-free catalog endpoint yet; a zero-config public metadata catalog is planned and is not shipped yet.
- Filmo is optional and requires catalog query mode and an explicitly enabled `filmo.to` source. Text discovery works without mappings; canonical ID searches and Radarr grabs need published movie mappings.
- AniBridge does not translate Sonarr's "Anime/Absolute" numbering into provider seasons/episodes. Requests use the season/episode coordinates Sonarr sends; query mode can only use canonical episode mappings that the configured metadata service publishes.

## Known Limitations

- Anime specials/extras rely on metadata-backed AniWorld mapping and can still depend on provider layout changes.
- Provider sites control availability, language offers, and hosters. AniBridge cannot guarantee uptime, regional access, or a particular quality.
- Query mode is bounded: broad or deeply paged searches are rejected rather than truncated. See the [catalog query guide](https://anibridge-docs.zacklack.de/guide/catalog-query).
- Interactive search behavior in Prowlarr remains dependent on the client and provider results.

## Planned Features

- A zero-config official public metadata catalog (no user-entered URL or token)
- Broader RSS Sync support
- Toggleable WebUI

## Installation

### With Docker

```bash
docker compose -f docker/compose.yaml up -d
```

### From source

```bash
git clone https://github.com/zzackllack/AniBridge.git
cd AniBridge
# Install uv first if needed: https://docs.astral.sh/uv/getting-started/installation/
cd apps/api
uv sync --frozen
uv run python -m app.main
```

## Endpoints

- Torznab feed: `http://localhost:8000/torznab/api`
- qBittorrent API: `http://localhost:8000/api/v2`
- Health check: `http://localhost:8000/health`

Configure Prowlarr/Sonarr/Radarr to point at the Torznab feed. Downloads are placed in
`DOWNLOAD_DIR` as defined in the configuration. For further details see the [quickstart guide in the documentation.](https://anibridge-docs.zacklack.de/guide/quickstart)

### Search modes

| Mode | Search source | Default | Notes |
| --- | --- | --- | --- |
| `legacy` | Live provider scraping per search | Yes | Deprecated; still functional. AniWorld, s.to, megakino. |
| `query` | A collector's previously published metadata | No | Advanced/operator-configured. Bounded queries, canonical mappings, optional Filmo movies. |

Set `CATALOG_MODE=query` plus a collector origin, source ID, and exactly one bearer token source to opt in. JSON catalog config files are no longer supported; `CATALOG_CONFIG_FILE` fails startup. See [Catalog query mode](https://anibridge-docs.zacklack.de/guide/catalog-query) and [Environment](https://anibridge-docs.zacklack.de/api/environment).

## Networking Policy (Important)

> [!WARNING]
> Legacy in-app outbound proxy support was deprecated and removed. Route outbound traffic
> externally using a host VPN or a VPN sidecar (for example Gluetun).

- Recommended: Run in Docker with a VPN sidecar (e.g., Gluetun) and attach
  AniBridge to the same network namespace so all requests and downloads egress
  through the VPN.
- Alternative: Use a system-level VPN on the host where AniBridge runs.
- Legacy STRM proxy endpoints (`/strm/stream`, `/strm/proxy`) remain supported;
  query jobs use `/strm/catalog`.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process
for submitting pull requests.

## License

This project is licensed under the BSD 3-Clause License see the [LICENSE](LICENSE) file for details.

## Support

- Create an [issue](https://github.com/Zzackllack/AniBridge/issues) for bug reports or feature requests.
- Check our [security policy](SECURITY.md) for reporting vulnerabilities.

## Acknowledgments

- Thanks to phoenixthrush for providing a Library for his [AniWorld Downloader](https://github.com/phoenixthrush/AniWorld-Downloader)
