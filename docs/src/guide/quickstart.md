---
title: Quickstart
outline: deep
---

# Quickstart

Get AniBridge running locally and test the core endpoints.

## Prerequisites

- Python 3.12+
- ffmpeg/ffprobe available in PATH (recommended for accurate renaming)
- Node optional (for building docs only)

## Install and Run

::: code-group

```bash [uv]
uv venv && uv pip install -r requirements.txt
uv run python -m app.main
```

```bash [pip]
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.main
```

:::

The API listens on `http://localhost:8000`.

## Smoke Test

```bash
curl -sS http://localhost:8000/health
# {"status":"ok"}
```

## Minimal Environment (optional)

Create `.env` or export env vars:

```bash
export DOWNLOAD_DIR=./data/downloads/anime
export DATA_DIR=./data
export MAX_CONCURRENCY=3
```

See all options in [Environment](/api/environment).

## Next Steps

- Configure Prowlarr with the Torznab URL: `http://localhost:8000/torznab/api`
- Configure Sonarr with the qBittorrent base URL: `http://localhost:8000/api/v2`
- Review detailed [Endpoints](/api/endpoints) and [Integrations](/integrations/prowlarr)

