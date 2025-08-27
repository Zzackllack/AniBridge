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

