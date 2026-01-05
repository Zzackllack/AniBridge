---
title: Networking & Proxies
outline: deep
---

# Networking & Proxies

> [!WARNING]
> Proxy support is experimental and may be unreliable with some providers/CDNs (link extraction can fail or downloads may be blocked). For production use, prefer a full VPN tunnel (system‑level) or run AniBridge inside Docker attached to a VPN sidecar like Gluetun. Do not rely on the in‑app proxy alone for consistent operation.

AniBridge can route all outbound HTTP/HTTPS requests and downloads through an HTTP/HTTPS or SOCKS proxy (e.g., a local SOCKS5 client from a VPN provider like NordVPN).

This applies to:
- Title index fetches (AniWorld and Serienstream alphabet pages)
- Megakino domain resolution and health checks
- Update checks (GitHub / GHCR)
- Provider page access via the `aniworld` library
- Downloads and probes performed by `yt-dlp`

## Quick Start

Set the following in your `.env` and restart AniBridge (experimental):

```ini
PROXY_ENABLED=true
PROXY_URL=socks5h://127.0.0.1:1080
PROXY_FORCE_REMOTE_DNS=true
PROXY_IP_CHECK_INTERVAL_MIN=30
```

- Use `socks5h` for remote DNS to avoid local DNS leaks via the proxy. Remote DNS is enabled by default for SOCKS unless explicitly disabled with `PROXY_FORCE_REMOTE_DNS=false`.
- For HTTP proxies, use e.g. `http://127.0.0.1:8080`.

If your proxy requires authentication:

```ini
PROXY_URL=socks5h://user:pass@proxy-host:1080
```

To bypass the proxy for certain hosts:

```ini
NO_PROXY=localhost,127.0.0.1
```

## Per-Protocol Overrides

If you need separate proxies for HTTP vs HTTPS, override per-protocol URLs:

```ini
HTTP_PROXY_URL=http://127.0.0.1:8080
HTTPS_PROXY_URL=socks5h://127.0.0.1:1080
```

`PROXY_URL` is used as a common default when the per-protocol values are not set.

## Credentials

If your proxy requires authentication (e.g., NordVPN SOCKS5 service credentials), either embed them in the URL:

```ini
PROXY_URL=socks5h://USERNAME:PASSWORD@proxy.nordvpn.com:1080
```

or set split fields (AniBridge builds `PROXY_URL` automatically):

```ini
PROXY_HOST=proxy.nordvpn.com
PROXY_PORT=1080
PROXY_SCHEME=socks5h
PROXY_USERNAME=USERNAME
PROXY_PASSWORD=PASSWORD
```

## Environment Application

When `PROXY_APPLY_ENV=true`, AniBridge sets `HTTP_PROXY`, `HTTPS_PROXY`, and `NO_PROXY` in the process environment (uppercase and lowercase). This ensures third‑party libraries respect the proxy automatically. It also sets `ALL_PROXY`/`all_proxy` for tools that honor the generic proxy variable.

## TLS Verification

In enterprise networks with TLS‑terminating proxies, you may need to disable certificate verification for metadata fetches:

```ini
PROXY_DISABLE_CERT_VERIFY=true
```

This does not affect `yt-dlp`’s own certificate handling for media downloads.

## IP Visibility

When `PROXY_ENABLED=true`, AniBridge periodically logs the current public IP as seen by outbound requests. Control the interval with `PROXY_IP_CHECK_INTERVAL_MIN` (set to `0` to disable). This helps verify that traffic is flowing through your proxy/VPN.

## Scope Control

Some providers block VPN endpoints. If you encounter provider errors only when proxying, narrow the scope:

```ini
# Only proxy yt-dlp (media fetches); provider pages go direct
PROXY_SCOPE=ytdlp

# Or only proxy HTTP clients; yt-dlp goes direct
PROXY_SCOPE=requests
```

Default is `PROXY_SCOPE=all`.

## Requirements

SOCKS proxies require `PySocks`, which is included in AniBridge’s runtime dependencies.
