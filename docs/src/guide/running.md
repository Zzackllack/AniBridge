---
title: Running
outline: deep
---

# Running AniBridge

::: danger Legal Disclaimer
Read the [Legal Disclaimer](/legal) first. Ensure your usage complies with applicable laws and site policies.
:::

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

## Behind a VPN (Docker + Gluetun)

When using `network_mode: service:gluetun`, multiple containers share the same network namespace. They cannot bind the same internal port. Configure a unique port per service and expose it via the VPN container’s port mappings.

- Set a unique port using env vars in AniBridge:

```ini
ANIBRIDGE_PORT=8083
ANIBRIDGE_HOST=0.0.0.0
```

- Map that port on the Gluetun container to your host, for example:

```yaml
services:
  gluetun:
    image: qmcgaw/gluetun
    ports:
      - "8083:8083/tcp"  # expose AniBridge via VPN
  anibridge:
    image: ghcr.io/zzackllack/anibridge:latest
    network_mode: "service:gluetun"  # share network with gluetun
    environment:
      - ANIBRIDGE_PORT=8083
      - ANIBRIDGE_HOST=0.0.0.0
      - DOWNLOAD_DIR=/data/downloads/anime
      - DATA_DIR=/data
    volumes:
      - ./data:/data
```

- Avoid `ANIBRIDGE_RELOAD` in production containers (development-only; reloader spawns extra process).

## Logs

- Structured logs to stdout/stderr (loguru)
- Terminal capture to `data/terminal-YYYY-MM-DD.log`

See [Logging](/developer/logging) for details.
