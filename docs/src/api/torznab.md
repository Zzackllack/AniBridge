---
title: Torznab API
outline: false
---

# Torznab API

Base: `/torznab/api`

Supported operations via `t`:

- `caps` — capabilities
- `search` — generic search (connectivity test supported)
- `tvsearch` — series episode search

> [!IMPORTANT]
> If `INDEXER_API_KEY` is set, pass `apikey=...` on every request.

<OASpec :tags="['Torznab']" :group-by-tags="true" hide-info hide-servers hide-branding />

## Behavior Notes

- When `q` is empty and `TORZNAB_RETURN_TEST_RESULT=true`, a synthetic test item is returned for connectivity checks.
- For a query, AniBridge resolves the slug across all enabled catalogues (AniWorld + Serienstream/s.to + megakino by default) and emits preview items for S01E01 across probable languages per site. Megakino is search-only, so queries must provide a slug or a megakino URL containing one.
- `tvsearch` emits items only for actually available languages/providers (using cached probe or live check).

## Magnet Payload

AniBridge crafts magnet URIs with embedded fields:

```text
magnet:?xt=urn:btih:{hash}&dn={release}&aw_slug={slug}&aw_s={S}&aw_e={E}&aw_lang={Language}&aw_provider={Provider}&aw_site={aniworld.to}
```

Optional variant field (used for STRM support):

```text
...&aw_mode=strm
```

For Serienstream releases the prefix switches to `sto_` (e.g., `sto_slug`, `sto_site=s.to`). Megakino releases still use the `aw_` prefix but include `aw_site=megakino` for routing. The qBittorrent shim parses these parameters when Sonarr posts to `/api/v2/torrents/add`.

## STRM Variants

When `STRM_FILES_MODE` is enabled (`both` or `only`), AniBridge emits additional Torznab items with a ` [STRM]` suffix. Selecting such an item causes AniBridge to create a `.strm` file (plain text, one URL line) instead of downloading the media file.

STRM variants intentionally report a normal-looking size (the same heuristic sizing as non-STRM items) so they are not rejected by Arr size filters.
