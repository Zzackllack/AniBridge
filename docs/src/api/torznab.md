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

Optional query parameters recognised by multiple operations:

- `sonarrAbsolute` (`true|false`) — hint that the request originated from an absolute-numbered series. AniBridge also auto-detects numeric identifiers in queries/episodes, but providing the hint keeps logging explicit.

> [!IMPORTANT]
> If `INDEXER_API_KEY` is set, pass `apikey=...` on every request.

## caps

```http
GET /torznab/api?t=caps
```

Returns an XML with categories, supported params, and limits.

## search

```http
GET /torznab/api?t=search&q={query}[&sonarrAbsolute=true]
```

- When `q` is empty and `TORZNAB_RETURN_TEST_RESULT=true`, a synthetic test item is returned for connectivity checks.
- For a title query, AniBridge resolves the slug against AniWorld titles and emits preview items for S01E01 across probable languages.
- Provide `sonarrAbsolute=true` (or end the query with the absolute episode number, e.g. `Naruto 005`) to preview absolute-numbered episodes. Returned items include `<torznab:attr name="absoluteNumber" value="005" />` so Sonarr/Prowlarr can reconcile the result.
- When an absolute number cannot be mapped and `ANIBRIDGE_FALLBACK_ALL_EPISODES=true`, the preview feed lists the entire catalogue instead of returning nothing. Each item retains its standard `SxxEyy` identifier and carries `absoluteNumber` (plus `anibridgeFallback=true`).

## tvsearch

```http
GET /torznab/api?t=tvsearch&q={title}&season={N}&ep={M}[&sonarrAbsolute=true]
```

Returns items only for actually available languages/providers (using cached probe or a live check). Every item contains:

- `<enclosure url="magnet:?..." type="application/x-bittorrent;x-scheme-handler/magnet" length="..." />`
- Torznab attrs: `magneturl`, `size`, `infohash`, `seeders`, `peers`, `leechers`
- `absoluteNumber` when the request originated from an absolute-numbered series
- `anibridgeFallback=true` when catalogue fallback supplied the entry because no direct mapping existed

## Magnet Payload

AniBridge crafts magnet URIs with embedded fields:

```text
magnet:?xt=urn:btih:{hash}&dn={release}&aw_slug={slug}&aw_s={S}&aw_e={E}&aw_lang={Language}&aw_provider={Provider}&aw_abs={ABS}
```

`aw_abs` is only present when AniBridge resolved an absolute-numbered request. The qBittorrent shim mirrors this metadata (see [qBittorrent API Shim](/api/qbittorrent)) when Sonarr posts to `/api/v2/torrents/add`.
