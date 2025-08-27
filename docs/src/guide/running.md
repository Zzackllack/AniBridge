---
title: Running
outline: deep
---

# Running AniBridge

You can run AniBridge directly with Python or via Docker Compose.

## Python

```bash
python -m app.main
# INFO: Uvicorn on http://0.0.0.0:8000
```

- Health: `GET /health`
- Docs: see [API](/api/endpoints) for curl examples

## Docker Compose

Create a minimal `docker-compose.yaml`:

```yaml
services:
  anibridge:
    image: ghcr.io/zzackllack/anibridge:latest
    container_name: anibridge
    ports:
      - "8000:8000"
    environment:
      - DOWNLOAD_DIR=/data/downloads/anime
      - DATA_DIR=/data
      - MAX_CONCURRENCY=3
    volumes:
      - ./data:/data
```

Bring it up:

```bash
docker compose up -d
curl -sS http://localhost:8000/health
```

## Logs

- Structured logs to stdout/stderr (loguru)
- Terminal capture to `data/terminal-YYYY-MM-DD.log`

See [Logging](/developer/logging) for details.

