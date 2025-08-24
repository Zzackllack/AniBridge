# AniBridge

AniBridge is a minimal FastAPI service that bridges anime streaming services (currently only aniworld) to automation tools. It exposes a fake Torznab feed and a fake qBittorrent-compatible API so that applications like Prowlarr/Sonarr can discover and download episodes automatically.

> [!CAUTION]
> ⚖️ Before using this software, please read the  
> [Legal Disclaimer](./LEGAL.md).

## Features

- **Torznab endpoint** that indexes available episodes from AniWorld.
- **qBittorrent API shim** allowing Prowlarr/Sonarr to enqueue downloads.
- **Background scheduler** with progress tracking for downloads.
- Simple `/health` endpoint for container or orchestration checks.

## Planned Features

- Support for non anime sites like s.to
- Interactive user search via Prowlarr (currently only search via Sonarr/API possible)
- Full support for RSS Sync
- Documentation, configuration instructions, and examples...
- Docker Image for easy deployment
- Better code structure and organization (refactoring, modularization, right now the code is a bit messy with comments in multiple languages, redundant code, etc. 😅)

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
