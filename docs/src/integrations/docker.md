---
title: Docker Compose
outline: deep
---

# Docker Compose

Deploy AniBridge alongside Prowlarr and Sonarr.

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
      - QBIT_PUBLIC_SAVE_PATH=/downloads
    volumes:
      - ./downloads:/data/downloads/anime
      - ./data:/data

  prowlarr:
    image: lscr.io/linuxserver/prowlarr:latest
    ports: ["9696:9696"]
    volumes: ["./prowlarr:/config"]
    depends_on: [anibridge]

  sonarr:
    image: lscr.io/linuxserver/sonarr:latest
    ports: ["8989:8989"]
    environment:
      - PUID=1000
      - PGID=1000
    volumes:
      - ./sonarr:/config
      - ./downloads:/downloads
    depends_on: [anibridge]
```

Now configure:

- Prowlarr Torznab URL: `http://anibridge:8000/torznab/api`
- Sonarr qBittorrent URL: `http://anibridge:8000/`
- Ensure the path Sonarr uses matches `QBIT_PUBLIC_SAVE_PATH`

