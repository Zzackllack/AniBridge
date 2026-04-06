---
layout: home
title: AniBridge Docs for FastAPI Anime Automation
titleTemplate: false
description: Deploy AniBridge as a FastAPI bridge for Prowlarr, Sonarr, and qBittorrent-compatible anime automation with AniWorld, Serienstream, and megakino providers.

hero:
  name: AniBridge
  text: FastAPI bridge for anime automation
  tagline: Torznab index + qBittorrent-compatible API that lets Prowlarr/Sonarr discover and download episodes from AniWorld, Serienstream (s.to), and megakino.
  image:
    src: /logo-384.png
    alt: AniBridge logo
    width: 384
    height: 384
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
    details: Works with Prowlarr, Sonarr, and Radarr using Torznab search plus qBittorrent-compatible download handoff.
    link: /integrations/clients/prowlarr
    linkText: Explore client integrations
  - icon: 🧵
    title: Background Scheduler
    details: Threaded job executor with progress, cancelation, and SSE event stream.
    link: /api/jobs
    linkText: Review jobs and events
  - icon: 📦
    title: Docker‑Ready
    details: Ship the server with Compose, mount data and logs, and configure the runtime with environment variables.
    link: /guide/running
    linkText: Read the running guide
  - icon: 📝
    title: Sensible Releases
    details: Smart file naming based on title, season, episode, quality, codec, and language so *arr tools parse releases cleanly.
    link: /guide/overview
    linkText: See how AniBridge works
  - icon: 🔎
    title: Quality Probing
    details: Preflight yt‑dlp checks per provider and language with semi‑cached availability.
    link: /integrations/providers/aniworld
    linkText: Compare provider behavior
  - icon: 📈
    title: Observability
    details: Structured logging (loguru) and terminal capture to daily rotating files in data/.
    link: /developer/logging
    linkText: Inspect logging and diagnostics
  - icon: ⚡
    title: Quickstart
    details: The shortest path from clone to working anime automation, including the first Torznab and qBittorrent-compatible setup steps.
    link: /guide/quickstart
    linkText: Open the quickstart
  - icon: ⚙️
    title: Configuration
    details: Review environment variables, catalog selection, networking assumptions, and runtime defaults before you harden a deployment.
    link: /guide/configuration
    linkText: Configure AniBridge
  - icon: 🛠️
    title: Troubleshooting
    details: Diagnose provider mismatches, missing episodes, API behavior, and runtime failures with concrete checks instead of guesswork.
    link: /guide/troubleshooting
    linkText: Troubleshoot common issues
  - icon: 📚
    title: API Reference
    details: Inspect the Torznab endpoint, qBittorrent shim, job APIs, STRM proxy behavior, and environment contract in one place.
    link: /api/overview
    linkText: Browse the API reference
  - icon: 🧩
    title: Provider Guides
    details: Compare AniWorld, S.to, and Megakino behavior for slugs, episodes, language mapping, and provider-controlled limitations.
    link: /integrations/providers/sto
    linkText: Read provider guides
  - icon: 🏗️
    title: Architecture
    details: Understand how AniBridge turns provider-backed discovery into stable automation workflows for *arr clients and download jobs.
    link: /developer/architecture
    linkText: See the architecture
---
