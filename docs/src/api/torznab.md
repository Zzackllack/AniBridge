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
- `movie` / `movie-search` — movie-focused search

> [!IMPORTANT]
> If `INDEXER_API_KEY` is set, pass `apikey=...` on every request.

## Query Parameters

- Common: `t`, `apikey`, `q`, `cat`, `offset`, `limit`
- `tvsearch`: `season`, optional `ep`
- Optional ID hints for specials mapping:
  `tvdbid`, `tmdbid`, `imdbid`, `rid`, `tvmazeid`

## Operations

<ApiOperations :tags="['Torznab']" hide-branding />

## Behavior Notes

- When `q` is empty and `TORZNAB_RETURN_TEST_RESULT=true`, a synthetic
  test item is returned for connectivity checks.
- For a query, AniBridge resolves the slug across all enabled
  catalogues (AniWorld + Serienstream/s.to + megakino by default) and
  emits preview items for S01E01 across probable languages per site.
  Megakino is search-only, so queries must provide a slug or a
  megakino URL containing one.
- `tvsearch` has two explicit modes:
  - `season` + `ep`: episode-search mode (single requested episode path).
  - `season` without `ep`: season-search mode (enumerates episodes and emits
    one or more items per discovered episode).
- Season-search episode discovery is metadata-first, then merges cached episode
  hints, then falls back to bounded sequential probing when needed.
- `limit` is a hard cap on emitted `<item>` elements. For multi-language or
  STRM dual-item seasons, increase `limit` if you want more complete results.
- `tvsearch` emits items only for actually available languages/providers
  (using cached probe or live check).
- For AniWorld specials/extras (`/filme`), AniBridge applies
  metadata-backed mapping to map Sonarr's requested special
  numbering/title to AniWorld's source `film-N` entries when they
  diverge.
- Release titles always keep the Sonarr-facing alias numbering (for
  example `S00E05`) even when AniWorld source probe/download uses a
  different `film-N` index. This keeps grab-time and import-time
  episode parsing consistent.

## Magnet Payload

AniBridge crafts magnet URIs with embedded fields:

```text
magnet:?xt=urn:btih:{hash}&dn={release}&aw_slug={slug}&aw_s={S}&aw_e={E}&aw_lang={Language}&aw_provider={Provider}&aw_site={aniworld.to}
```

Optional variant field (used for STRM support):

```text
...&aw_mode=strm
```

For Serienstream releases the prefix switches to `sto_`
(e.g., `sto_slug`, `sto_site=s.to`). Megakino releases still use the
`aw_` prefix but include `aw_site=megakino` for routing. The
qBittorrent shim parses these parameters when Sonarr posts to
`/api/v2/torrents/add`.

## STRM Variants

When `STRM_FILES_MODE` is enabled (`both` or `only`), AniBridge emits
additional Torznab items with a ` [STRM]` suffix. Selecting such an
item causes AniBridge to create a `.strm` file (plain text, one URL
line) instead of downloading the media file.

When `STRM_PROXY_MODE=proxy`, the `.strm` file points to the AniBridge
proxy endpoint (`/strm/stream`) rather than a provider/CDN URL. In
`direct` mode it writes the resolved provider URL directly.

STRM variants intentionally report a normal-looking size (the same
heuristic sizing as non-STRM items) so they are not rejected by Arr
size filters.

::: warning
Sonarr can occasionally reject `.strm` imports with “No audio tracks detected” even when playback works. If this
appears, use manual import or disable “Analyze video files” in Sonarr. See
[Issue #50](https://github.com/zzackllack/anibridge/issues/50).
:::
