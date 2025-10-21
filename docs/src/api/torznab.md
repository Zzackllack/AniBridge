---
title: Torznab API
outline: deep
---

# Torznab API

Base: `/torznab/api`

Supported operations via `t`:

- `caps` — capabilities
- `search` — generic search (connectivity test supported)
- `tvsearch` — series episode search

> [!IMPORTANT]
> If `INDEXER_API_KEY` is set, pass `apikey=...` on every request.

## caps

```http
GET /torznab/api?t=caps
```

Returns an XML with categories, supported params, and limits.

## search

```http
GET /torznab/api?t=search&q={query}
```

- When `q` is empty and `TORZNAB_RETURN_TEST_RESULT=true`, a synthetic test item is returned for connectivity checks.
- For a query, AniBridge resolves the slug across all enabled catalogues (AniWorld + Serienstream/s.to by default) and emits preview items for S01E01 across probable languages per site.

## tvsearch

```http
GET /torznab/api?t=tvsearch&q={title}&season={N}&ep={M}
```

Emits items only for actually available languages/providers (using cached probe or live check). Items include:

- `<enclosure url="magnet:?..." type="application/x-bittorrent;x-scheme-handler/magnet" length="..." />`
- Torznab attrs: `magneturl`, `size`, `infohash`, `seeders`, `peers`, `leechers`

## Magnet Payload

AniBridge crafts magnet URIs with embedded fields:

```text
magnet:?xt=urn:btih:{hash}&dn={release}&aw_slug={slug}&aw_s={S}&aw_e={E}&aw_lang={Language}&aw_provider={Provider}&aw_site={aniworld.to}
```

For Serienstream releases the prefix switches to `sto_` (e.g., `sto_slug`, `sto_site=s.to`). The qBittorrent shim parses these parameters when Sonarr posts to `/api/v2/torrents/add`.

