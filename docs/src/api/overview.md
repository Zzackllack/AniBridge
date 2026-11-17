---
title: API Reference
outline: false
---

# API Reference

This section is organized around operation pages (one page per endpoint). Use the sidebar or the index below to jump to the operation you need.

## Base URL

`http://localhost:8000` (default development host)

> [!IMPORTANT]
> If `INDEXER_API_KEY` is set, include `apikey=...` on every Torznab request.

> [!TIP]
> STRM proxy endpoints (`/strm/*`) use their own auth settings via
> `STRM_PROXY_AUTH`.

`CATALOG_MODE` changes what backs `/torznab/api` and `/api/v2`:

- `legacy` (default): live provider scraping plus the legacy job API.
- `query`: bounded collector metadata search plus durable local jobs. Query mode
  also exposes optional `/api/v1/jobs/*` management endpoints when
  `MANAGEMENT_API_TOKEN` is set.

Query mode is advanced and operator-configured; there is no hosted zero-config
metadata catalog yet. See [Catalog Query Mode](/guide/catalog-query).

## Browse Operations

The interactive operation pages describe the legacy HTTP surface. Query-mode
semantics and management endpoints are documented in
[Torznab](/api/torznab), [qBittorrent](/api/qbittorrent) and [Jobs](/api/jobs).

<ApiOperations hide-branding />
