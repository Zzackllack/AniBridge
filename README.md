# AniBridge

AniBridge is a FastAPI bridge that exposes:
- Torznab endpoints for *arr indexer flows
- qBittorrent-compatible endpoints for import/download orchestration
- STRM generation and STRM proxy streaming endpoints (`/strm/*`)

## Networking Policy

AniBridge no longer supports the legacy in-app outbound proxy (`PROXY_*`).

Supported approach:
- external VPN routing (host VPN, VPN sidecar such as Gluetun, or external network policy)

This change does **not** remove STRM proxy functionality.

## Configuration

See:
- `/.env.example`
- `/docs/src/guide/configuration.md`
- `/docs/src/guide/networking.md`

## Local Development

- Tests: `pytest`
- Format: `ruff format app`
- Docs build: `pnpm --prefix docs run build`
