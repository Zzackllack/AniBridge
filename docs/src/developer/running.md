---
title: Running Locally
outline: deep
---

# Running Locally

## Dev server

```bash
python -m app.main
```

- Reload is auto-enabled in dev; disabled for packaged runs
- Set `ANIBRIDGE_RELOAD=1` to force reload

## Docker dev stack

For the full Sonarr/Radarr/Prowlarr workflow in containers, use the development compose file in watch mode:

```bash
docker compose -f docker/docker-compose.dev.yaml up --watch
```

- Python source changes under `app/` are synced into the running AniBridge container.
- Uvicorn reload picks those changes up without rebuilding the whole image.
- Changes to `pyproject.toml`, `uv.lock`, `Dockerfile`, `docker/entrypoint.sh`, `VERSION`, or `alembic.ini` trigger an AniBridge image rebuild automatically.
- On Windows/Docker Desktop, shell scripts must use LF line endings. The image normalizes `docker/entrypoint.sh` during build, and the repo ships `.gitattributes` rules to keep shell and Docker files on LF.

## Envs

Use `.env` or export vars. See [Environment](/api/environment).

## Useful curl

::: code-group
```bash [health]
curl -sS localhost:8000/health
```
```bash [torznab caps]
curl -sS 'http://localhost:8000/torznab/api?t=caps'
```
```bash [enqueue job]
curl -sS -X POST localhost:8000/downloader/download \
  -H 'content-type: application/json' \
  -d '{"slug":"your-slug","season":1,"episode":1,"language":"German Dub"}'
```
:::
