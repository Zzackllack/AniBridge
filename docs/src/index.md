---
layout: home

hero:
  name: AniBridge
  text: FastAPI bridge for anime automation
  tagline: Torznab index + qBittorrent-compatible API that lets Prowlarr/Sonarr discover and download episodes from AniWorld, Serienstream (s.to), and megakino.
  image:
    src: /logo.png
    alt: AniBridge logo
  actions:
    - theme: brand
      text: Get Started
      link: /guide/quickstart
    - theme: alt
      text: API Reference
      link: /api/overview
    - theme: alt
      text: GitHub
      link: https://github.com/zzackllack/AniBridge

features:
  - icon: 🧭
    title: Drop‑in Integrations
    details: Works with Prowlarr and Sonarr using Torznab and qBittorrent API shims.
  - icon: 🧵
    title: Background Scheduler
    details: Threaded job executor with progress, cancelation, and SSE event stream.
  - icon: 📦
    title: Docker‑Ready
    details: Ship the server with Compose, mount data and logs, and configure via env.
  - icon: 📝
    title: Sensible Releases
    details: Smart file naming based on title, season, episode, quality, codec, and language.
  - icon: 🔎
    title: Quality Probing
    details: Preflight yt‑dlp checks per provider and language with semi‑cached availability.
  - icon: 📈
    title: Observability
    details: Structured logging (loguru) and terminal capture to daily rotating files in data/.
---
