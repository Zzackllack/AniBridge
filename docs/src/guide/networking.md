---
title: Networking & VPN
outline: deep
---

# Networking & VPN

AniBridge no longer supports the legacy in-app outbound proxy (`PROXY_*`).

Only external routing is supported:
- host/system VPN
- Docker VPN sidecar (for example Gluetun)
- external network-layer routing or firewall policy

## Recommended Setup

Use a VPN sidecar and share its network namespace with AniBridge.

```yaml
services:
  gluetun:
    image: qmcgaw/gluetun:latest
    ports:
      - "8000:8000/tcp"

  anibridge:
    image: ghcr.io/zzackllack/anibridge:latest
    network_mode: "service:gluetun"
    environment:
      - ANIBRIDGE_HOST=0.0.0.0
      - ANIBRIDGE_PORT=8000
```

## Public IP Monitor

AniBridge can periodically log the active public IP so you can verify egress.

```ini
PUBLIC_IP_CHECK_ENABLED=true
PUBLIC_IP_CHECK_INTERVAL_MIN=30
```

Set `PUBLIC_IP_CHECK_INTERVAL_MIN=0` to disable checks.

## Removed In-App Proxy Variables

The following are removed and ignored when set:

- `PROXY_ENABLED`
- `PROXY_URL`
- `HTTP_PROXY_URL`
- `HTTPS_PROXY_URL`
- `ALL_PROXY_URL`
- `PROXY_HOST`
- `PROXY_PORT`
- `PROXY_SCHEME`
- `PROXY_USERNAME`
- `PROXY_PASSWORD`
- `NO_PROXY`
- `PROXY_FORCE_REMOTE_DNS`
- `PROXY_DISABLE_CERT_VERIFY`
- `PROXY_APPLY_ENV`
- `PROXY_IP_CHECK_INTERVAL_MIN`
- `PROXY_SCOPE`

## STRM Proxy Is Unchanged

This removal does not affect STRM proxy endpoints (`/strm/*`).

See [STRM Proxy](/api/strm-proxy).
