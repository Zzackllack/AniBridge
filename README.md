# AniBridge

AniBridge is a minimal FastAPI service that bridges anime sources to automation tools. It exposes
an anime-focused Torznab feed and a qBittorrent-compatible API so that applications like
Prowlarr can discover and download episodes automatically.

## Features

- **Torznab endpoint** that indexes available episodes from AniWorld.
- **qBittorrent API shim** allowing Prowlarr to enqueue downloads.
- **Background scheduler** with progress tracking for downloads.
- Simple `/health` endpoint for container or orchestration checks.

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
uvicorn app.main:app --reload
```

## Usage

- Torznab feed: `http://localhost:8000/torznab`
- qBittorrent API: `http://localhost:8000/api/v2`
- Health check: `http://localhost:8000/health`

Configure Prowlarr or other automation tools to point at the Torznab feed. Downloads are placed in
`DOWNLOAD_DIR` as defined in the configuration.

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process
for submitting pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- Create an [issue](../../issues) for bug reports or feature requests.
- Check our [security policy](SECURITY.md) for reporting vulnerabilities.

## Acknowledgments

- Thanks to the FastAPI community and upstream libraries.
- Inspired by the desire to automate anime downloads.
