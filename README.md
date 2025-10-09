# AniBridge

<a href="https://anibridge-docs.zacklack.de" target="_blank" style="float: right;">
  <img src=".github/img/logo.png" width="164" height="164" alt="AniBridge Logo" align="right" />
</a>

AniBridge is a minimal FastAPI service that bridges anime streaming services (currently only aniworld) to automation tools. It exposes a fake Torznab feed and a fake qBittorrent-compatible API so that applications like Prowlarr/Sonarr can discover and download episodes automatically.

> [!CAUTION]
> ⚖️ Before using this software, please read the  
> [Legal Disclaimer](./LEGAL.md).

## Features

- **Torznab endpoint** that indexes available episodes from AniWorld.
- **qBittorrent API shim** allowing Prowlarr/Sonarr to enqueue downloads.
- **Background scheduler** with progress tracking for downloads.
- **Absolute numbering support** for Sonarr anime libraries, including optional catalogue fallback when a mapping cannot be resolved.
- Simple `/health` endpoint for container or orchestration checks.
- Docker Image for easy deployment

## Currently work-in-progress / TODO

- Better code structure and organization (refactoring, modularization, right now the code is a bit messy with comments in multiple languages, redundant code, etc. 😅)
- Documentation, configuration instructions, and examples...

## Planned Features

- Support for non anime sites like s.to
- Interactive user search via Prowlarr (currently only search via Sonarr/API possible)
- Full support for RSS Sync
- Toggleable WebUI

## Installation

### With Docker

```bash
docker compose up -d
```

### From source

```bash
git clone https://github.com/zzackllack/AniBridge.git
cd AniBridge
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

## Endpoints

- Torznab feed: `http://localhost:8000/torznab`
- qBittorrent API: `http://localhost:8000/api/v2`
- Health check: `http://localhost:8000/health`

Configure Prowlarr or other automation tools to point at the Torznab feed. Downloads are placed in
`DOWNLOAD_DIR` as defined in the configuration.

## Networking & Proxy (Important)

> [!WARNING]
> Proxy support is experimental and may be unreliable with some providers/CDNs. For production use, prefer running AniBridge behind a full VPN tunnel (system‑level) or inside a container attached to a VPN sidecar like Gluetun. Do not rely on the in‑app proxy for consistent operation.

- Recommended: Run in Docker with a VPN container (e.g., Gluetun) and attach AniBridge to the same network so all HTTP requests and downloads egress through the VPN.
- Alternative: Use a system‑level VPN on the host where AniBridge runs.
- The built‑in proxy toggles are in active development and can fail to extract links or be blocked by hosters/CDNs.

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
