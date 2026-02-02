---
title: Quickstart
outline: deep
---

# Quickstart

Get AniBridge running in minutes. Pick one of the methods below.

## Video walkthrough

<div style="position: relative; width: 100%; padding-top: 56.25%;">
  <iframe
    src="https://www.youtube.com/embed/gbc24WHm7U4"
    title="AniBridge Quickstart Video"
    frameborder="0"
    allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
    referrerpolicy="strict-origin-when-cross-origin"
    allowfullscreen
    style="position: absolute; inset: 0; width: 100%; height: 100%;"
  ></iframe>
</div>

::: danger Legal & Ethics
Read the short [Legal Disclaimer](/legal) before continuing. AniBridge does not host or provide content. You are responsible for compliance with laws and site terms in your jurisdiction.
:::

## Option A — Docker (recommended)

The simplest and most reliable way to run AniBridge.

### Minimal Compose

```yaml
services:
  anibridge:
    image: ghcr.io/zzackllack/anibridge:latest
    container_name: anibridge
    ports:
      - "8000:8000"   # host:container
    environment:
      - QBIT_PUBLIC_SAVE_PATH=/downloads
    volumes:
      - ./downloads:/data/downloads   # host path → container path
      - ./data:/data                        # DB, logs
```

Verify:

```bash
docker compose up -d
curl -sS http://localhost:8000/health
# {"status":"ok"}
```

::: tip Sonarr/Prowlarr URLs

- Torznab: `http://anibridge:8000/torznab/api`
- qBittorrent base: `http://anibridge:8000/`
:::

### With Gluetun (VPN sidecar)

Recommended for privacy and stability. AniBridge shares the VPN network namespace and is exposed via Gluetun’s port mapping.

```yaml
services:
  gluetun:
    image: qmcgaw/gluetun:latest
    container_name: gluetun
    cap_add: ["NET_ADMIN"]
    ports:
      - "8000:8000/tcp"   # expose AniBridge through the VPN container
    environment:
      # Fill according to the Gluetun docs for your provider
      - VPN_SERVICE_PROVIDER=custom     # or your provider name
      - VPN_TYPE=wireguard              # or openvpn
      - WIREGUARD_PRIVATE_KEY=...       # required for WireGuard
      - WIREGUARD_ADDRESSES=10.64.0.2/32
      # - SERVER_COUNTRIES=...         # example for provider selection

  anibridge:
    image: ghcr.io/zzackllack/anibridge:latest
    container_name: anibridge
    network_mode: "service:gluetun"   # route all traffic via Gluetun
    environment:
      - QBIT_PUBLIC_SAVE_PATH=/downloads
    volumes:
      - ./downloads:/data/downloads
      - ./data:/data
```

::: warning Port collisions inside VPN namespace
When multiple apps share Gluetun’s network, each must listen on a unique internal port. AniBridge defaults to `8000`. If you need a different port, set `ANIBRIDGE_PORT` and map the same port on the Gluetun service.
:::

## Option B — Bare metal (prebuilt releases)

Download the binary for your OS/arch from GitHub Releases and run it.

```bash
# macOS (Apple Silicon example)
curl -L -o anibridge.tar.gz \
  "https://github.com/zzackllack/AniBridge/releases/latest/download/anibridge-macos-arm64.tar.gz"
tar -xzf anibridge.tar.gz && chmod +x anibridge
./anibridge
```

Place a `.env` file next to the binary if you need to customize paths. See [Environment](/api/environment).

## Option C — Python (from source)

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

## Next Steps

- Configure Prowlarr (Torznab): `http://localhost:8000/torznab/api`
- Configure Sonarr (qBittorrent): `http://localhost:8000/`
- Browse [Environment](/api/environment) for available settings
- See [Integrations → Sonarr](/integrations/sonarr), [Integrations → Radarr](/integrations/radarr ) and [Integrations → Prowlarr](/integrations/prowlarr) for setup guides
