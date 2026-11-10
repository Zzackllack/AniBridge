---
title: Torznab API
outline: false
---

# Torznab API

Base: `/torznab/api`

Supported operations via `t`:

- `caps` — capabilities
- `search` — generic search
- `tvsearch` — series episode search
- `movie` / `movie-search` — movie-focused search

> [!IMPORTANT]
> If `INDEXER_API_KEY` is set, pass `apikey=...` on every request.

## Query Parameters

- Common: `t`, `apikey`, `q`, `cat`, `offset`, `limit`, `maxage`
- `tvsearch`: `season`, optional `ep`
- Movie search: optional `year`
- ID hints: `tvdbid`, `tmdbid`, `imdbid`
- Legacy-only ID hints: `rid`, `tvmazeid`

## Operations

<ApiOperations :tags="['Torznab']" hide-branding />

## Legacy Mode Behavior

Legacy mode is the default and is deprecated. It scrapes providers during each
search.

- With empty `q` and `TORZNAB_RETURN_TEST_RESULT=true`, `t=search` returns a
  synthetic connectivity item.
- A query resolves the slug across enabled catalogues and emits preview items for
  S01E01 across probable languages per site.
- Megakino is search-only; legacy queries must provide a slug or a megakino URL
  containing one.
- `tvsearch` has two explicit modes:
  - `season` + `ep`: episode search.
  - `season` without `ep` (or `ep<=0`): season search.
- Season search is metadata-first and merges cached episode hints. The default
  `TORZNAB_SEASON_SEARCH_MODE=fast` skips live fallback probing so Sonarr season
  searches stay responsive.
- `limit` is a hard cap on emitted `<item>` elements.
- `t=movie` / `movie-search` uses the Megakino movie preview path.
- For AniWorld specials/extras (`/filme`), metadata-backed mapping can translate
  Sonarr's absolute special numbering to a source `film-N` entry while release
  titles keep the Sonarr-facing alias numbering (for example `S00E05`).

## Query Mode Behavior

Query mode replaces live scraping with metadata previously published by a
collector. Set `CATALOG_MODE=query` and configure the connection described in
[Catalog Query Mode](/guide/catalog-query). Media downloads remain local.

- `t=caps` works during a metadata outage.
- `t=search` with empty `q` is a bounded **recent** page, not a synthetic test
  item. `maxage` is 1–30 days (default 30); the page is capped at 100 rows.
- `t=search` with `q` matches collected titles and aliases.
- `t=tvsearch` accepts `q` or an ID, with optional `season`/`ep`. Without
  `season`/`ep`, a text or ID request returns mapped episodes across seasons
  (bounded by the page limits). Season/episode filters use canonical coordinates
  when published.
- `t=movie` / `movie-search` returns movie rows, optionally filtered by `year` or
  an ID.
- `limit` is 1–100 (default 100); `offset` is 0–10000. Title discovery matches at
  most 200 candidates, and native expansion is capped at 2,000 releases per title
  set. Broader requests return HTTP 400 `query_too_broad`.
- `rid` and `tvmazeid` are unsupported in query mode.
- Query items report `size="0"` because collected metadata does not measure the
  media file. Adjust client size filters if needed.

### Partial results, stale data, and errors

- A failed provider does not erase reachable providers. The response includes
  `X-AniBridge-Catalog-Partial: true` and
  `X-AniBridge-Catalog-Unavailable: <provider>,...`.
- If no provider succeeds, or any provider fails and the remaining results are
  empty, AniBridge returns HTTP 503 with Torznab error code 900 and
  `Retry-After` instead of an empty success.
- A prior positive page may be served stale for up to 24 hours during transport
  failure, timeout, HTTP 429, or HTTP 503. It is marked
  `X-AniBridge-Catalog-Stale: true` with
  `X-AniBridge-Catalog-Age: <seconds>`. Empty pages are never served from stale
  cache to hide an outage.
- `X-AniBridge-Mapping: unresolved` means an ID search matched no published
  mapping. `X-AniBridge-Mapping: partial` means selected rows lack canonical
  coordinates. Text search can still return unmapped titles.
- Cache and stale behavior are described in
  [Catalog Query Mode](/guide/catalog-query#cache-stale-data-and-outages).

### Numbering

Query mode emits canonical `SxxEyy` numbering when the collector publishes an
episode mapping; otherwise it emits the provider's native season/episode. It does
not guess mappings and does not translate Sonarr "Anime/Absolute" requests into
provider seasons/episodes. Movie titles append the observed year.

Query labels restore the provider release-group suffix (`-ANIWORLD`, `-STO`,
`-MEGAKINO`, `-FILMO`) once, before the `.STRM` marker. The suffix is display and
durable output metadata, not part of the magnet payload, so adding it does not
change the infohash or invalidate queued aliases.

## Magnet Payload

### Legacy payload

Legacy items embed provider fields in the magnet:

```text
magnet:?xt=urn:btih:{hash}&dn={release}&aw_slug={slug}&aw_s={S}&aw_e={E}&aw_lang={Language}&aw_provider={Provider}&aw_site={aniworld.to}
```

Optional variant field (used for STRM support):

```text
...&aw_mode=strm
```

For Serienstream releases the prefix switches to `sto_`
(e.g., `sto_slug`, `sto_site=s.to`). Megakino releases still use the
`aw_` prefix but include `aw_site=megakino` for routing.

### Query payload

Query items use an opaque, versioned magnet payload (`ab_v=3`) that carries the
release identity, canonical mapping when available, and — for Filmo — the selected
source variant and declared audio/subtitle/quality metadata. Do not edit these
fields by hand. The qBittorrent shim validates the payload, rejects disabled
providers or identity conflicts, and admits a durable local job.

## Categories

- AniWorld episodes: `TORZNAB_CAT_ANIME` (default `5070`)
- Other series episodes: `5000`
- Movies (including Filmo): `TORZNAB_CAT_MOVIE` (default `2000`)

## Filmo Attributes

Filmo items expose declared source evidence separately from measured media:

- `anibridge_host`, `anibridge_source_id`
- `anibridge_audio_languages`, `anibridge_audio_role`
- `anibridge_subtitle_mode`, `anibridge_subtitle_languages` when known
- `anibridge_source_claim`, `anibridge_resolution_claim`
- `anibridge_measured_resolution` when a measured height exists
- One `language` attribute per known audio language; `und` is omitted

Only VOE and Byse offers are selectable. Quality and subtitle claims are declared
by the source, not measured from the file. See
[Filmo](/integrations/providers/filmo).

## STRM Variants

When `STRM_FILES_MODE` is enabled (`both` or `only`), AniBridge emits additional
Torznab items with a ` [STRM]` legacy suffix or a `.STRM` query-mode suffix.
Selecting such an item creates a `.strm` file (plain text, one URL line) instead
of downloading media.

When `STRM_PROXY_MODE=proxy`, the `.strm` file points to an AniBridge streaming
endpoint rather than a provider/CDN URL. In `direct` mode it writes the resolved
provider URL directly. Query jobs use `/strm/catalog`; legacy jobs use
`/strm/stream`. See [STRM Proxy](/api/strm-proxy).

::: warning
Sonarr can occasionally reject `.strm` imports with “No audio tracks detected” even when playback works. If this
appears, use manual import or disable “Analyze video files” in Sonarr. See
[Issue #50](https://github.com/zzackllack/anibridge/issues/50).
:::
