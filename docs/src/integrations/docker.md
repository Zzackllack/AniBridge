---
title: Docker Compose
outline: deep
---

# Docker Compose

::: danger Legal Disclaimer
Read the [Legal Disclaimer](/legal) before deploying. Ensure lawful use and compliance with service terms.
:::

Deploy AniBridge with a minimal Compose file. Add Prowlarr/Sonarr as needed.

```yaml
services:
  anibridge:
    image: ghcr.io/zzackllack/anibridge:latest
    container_name: anibridge
    ports:
      - "8000:8000"
    environment:
      - QBIT_PUBLIC_SAVE_PATH=/downloads
    volumes:
      - ./downloads:/data/downloads/anime
      - ./data:/data
```

Now configure:

- Prowlarr Torznab URL: `http://anibridge:8000/torznab/api`
- Sonarr qBittorrent URL: `http://anibridge:8000/`
- Ensure the path Sonarr uses matches `QBIT_PUBLIC_SAVE_PATH`

### With Gluetun (VPN container)

```yaml
services:
  gluetun:
    image: qmcgaw/gluetun:latest
    cap_add: ["NET_ADMIN"]
    ports:
      - "8000:8000/tcp"  # expose AniBridge via VPN
    environment:
      # Provide your VPN credentials/config per Gluetun docs
      - VPN_SERVICE_PROVIDER=custom
      - VPN_TYPE=wireguard
      - WIREGUARD_PRIVATE_KEY=...
      - WIREGUARD_ADDRESSES=10.64.0.2/32

  anibridge:
    image: ghcr.io/zzackllack/anibridge:latest
    network_mode: "service:gluetun"
    environment:
      - QBIT_PUBLIC_SAVE_PATH=/downloads
    volumes:
      - ./downloads:/data/downloads/anime
      - ./data:/data
```

::: warning Shared network notes
When using `network_mode: service:gluetun`, all services share Gluetun’s network. Expose AniBridge by mapping its port on the Gluetun service. If you change AniBridge’s internal port, update the Gluetun `ports` mapping accordingly.
:::
