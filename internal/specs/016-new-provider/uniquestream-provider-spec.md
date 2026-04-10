# AniBridge UniqueStream Provider Spec

Date: 2026-04-10
Status: Exploratory Draft
Scope: Deep provider analysis for `anime.uniquestream.net` and
`uniquestream.net`, architectural fit with AniBridge, implementation options,
recommended rollout plan, risks, and validation strategy

## 1. Purpose

This spec evaluates how AniBridge can add support for UniqueStream as a new
provider family.

UniqueStream is not one homogeneous target. It currently appears to consist of
two materially different systems:

- `anime.uniquestream.net` for anime, backed by a modern JSON API
- `uniquestream.net` for movies and TV, backed by WordPress, custom AJAX
  player loading, and a different content model

The central conclusion of this investigation is:

- the anime site is integration-ready and should be treated as the first real
  implementation target
- the main site is also technically integratable, but should be treated as a
  separate provider implementation with a higher maintenance and breakage risk
- AniBridge should not force both sites into one provider abstraction too early

This spec intentionally separates confirmed facts from inference and design
recommendations.

## 2. Current AniBridge Provider Architecture

AniBridge currently has two broad provider patterns.

### 2.1 AniWorld / s.to pattern

Files:

- `apps/api/app/providers/base.py`
- `apps/api/app/providers/aniworld/provider.py`
- `apps/api/app/providers/sto/provider.py`
- `apps/api/app/providers/sto/v2.py`
- `apps/api/app/utils/title_resolver.py`
- `apps/api/app/core/downloader/episode.py`
- `apps/api/app/core/downloader/provider_resolution.py`

Characteristics:

- provider catalog is discovered through HTML pages or alphabet indexes
- title resolution is slug-oriented
- stream resolution depends on AniWorld-style episode pages and downstream host
  providers
- playback probing is built around the AniWorld episode/provider model

### 2.2 Megakino pattern

Files:

- `apps/api/app/providers/megakino/provider.py`
- `apps/api/app/providers/megakino/client.py`
- `apps/api/app/utils/title_resolver.py`
- `apps/api/app/utils/probe_quality.py`

Characteristics:

- dedicated native client
- JSON-native provider behavior
- direct title search and media URL extraction
- custom integration path rather than forcing AniWorld assumptions

### 2.3 Architectural implication for UniqueStream

The anime site fits the Megakino pattern much more closely than the AniWorld
pattern.

The main site also does not fit the AniWorld pattern. Even though it is HTML
driven on the surface, the actual player contract is a WordPress AJAX flow, not
an AniWorld-style episode/provider redirect model.

Therefore:

- `anime.uniquestream.net` should be implemented as a dedicated native client
  and provider
- `uniquestream.net` should be implemented, if at all, as a second dedicated
  native client and provider
- a shared `uniquestream` namespace can exist, but only for common models and
  utilities, not by pretending both backends are the same

## 3. Research Method

This investigation combined:

- repository architecture inspection
- direct HTTP probing with browser-like user agents where required
- frontend bundle inspection for route and endpoint discovery
- live validation of search, browse, detail, episode, media, and player loading
  endpoints

This spec does not rely on Wappalyzer alone. Wappalyzer was directionally
useful, but the recommendations below are based on confirmed live behavior.

## 4. High-Level Findings

### 4.1 Confirmed summary

`anime.uniquestream.net`:

- exposes a usable JSON API under `/api/v1`
- exposes search, browse, series detail, season episodes, and media endpoints
- returns signed HLS playlists directly
- appears suitable for direct AniBridge integration

`uniquestream.net`:

- is WordPress-backed
- blocks the public REST index, but not all item and collection endpoints
- exposes searchable collection endpoints under `wp-json/wp/v2/*`
- uses per-page inline player config plus `wp-admin/admin-ajax.php` to load
  actual embeds
- is integratable, but with more moving parts and higher drift risk

### 4.2 Strategic conclusion

The correct implementation order is:

1. Ship anime support first.
2. Design shared abstractions only after anime behavior is stable.
3. Treat the main site as phase 2 or phase 3 work.

Trying to merge both into one first-pass provider would create avoidable
complexity and likely slow down the first useful release.

## 5. `anime.uniquestream.net` Deep Analysis

## 5.1 Stack and runtime characteristics

Confirmed from page runtime and frontend assets:

- frontend is Nuxt/Vue-based
- Cloudflare is in front
- runtime config exposes:
  - `API_BASE = https://anime.uniquestream.net/api/v1`
  - `WS_BASE = https://anime.uniquestream.net`
  - `COMMENTS_BASE = https://comments.uniquestream.net`

Important implication:

- the site intentionally ships a browser-consumable JSON API
- this is not hidden backend-only traffic
- integration does not need brittle HTML scraping for primary data paths

## 5.2 OpenAPI / Swagger discovery

Several typical OpenAPI paths were probed, including variants like:

- `/openapi.json`
- `/docs`
- `/swagger.json`

Result:

- no public OpenAPI or Swagger document was exposed
- these routes returned SPA HTML fallbacks instead of API schema output

Conclusion:

- the Pydantic-style validation error strongly suggests a modern Python API
  stack, but public schema discovery should not be assumed
- AniBridge should map only the endpoints it actually needs

## 5.3 Evidence of Python / Pydantic-style validation

You observed the error:

```json
{
  "msg": "Input should be a valid integer, unable to parse string as an integer",
  "input": "<offset>",
  "url": "https://errors.pydantic.dev/2.7/v/int_parsing"
}
```

That is highly consistent with Pydantic v2 validation output.

What this means:

- there is likely a Python backend with request validation
- FastAPI is plausible
- but FastAPI cannot be concluded with certainty from this error alone
- more importantly, AniBridge does not need that certainty to integrate

## 5.4 Confirmed anime API endpoints

### 5.4.1 Search

Confirmed endpoint:

```text
GET https://anime.uniquestream.net/api/v1/search?query=<query>&t=<type>&limit=<n>
```

Confirmed live examples:

```text
GET /api/v1/search?query=naruto&t=all&limit=5
GET /api/v1/search?query=naruto&t=series&limit=1
```

Observed response shape:

- top-level object with keys:
  - `series`
  - `movies`
  - `episodes`

Observed series item fields:

- `content_id`
- `title`
- `image`
- `type`
- `subbed`
- `dubbed`
- `seasons_count`
- `episodes_count`

Observed episode item fields:

- `content_id`
- `title`
- `image`
- `type`
- `series_title`
- `season_number`
- `season_display`
- `episode_number`
- `duration_ms`
- `is_clip`

Implementation relevance:

- this is sufficient for title lookup
- this is already better than AniWorld-style HTML title probing
- response separation by `series`, `movies`, and `episodes` gives AniBridge a
  natural path to content-kind-aware matching

### 5.4.2 Browse

Confirmed endpoint:

```text
GET https://anime.uniquestream.net/api/v1/videos/browse?offset=<offset>
```

Confirmed live example:

```text
GET /api/v1/videos/browse?offset=0
```

Observed response shape:

- top-level object with `data`
- each item in `data` includes:
  - `content_id`
  - `title`
  - `subbed`
  - `dubbed`
  - `info`
  - `image`
  - `image_loading`
  - `image_tall`
  - `image_tall_loading`
  - `type`

Observed types:

- `show`
- `movie`

Implementation relevance:

- useful for exploratory catalog sync if needed
- likely not required for first implementation if search is sufficient
- confirms the anime site supports both episodic and movie content

### 5.4.3 Series details

Confirmed endpoint:

```text
GET https://anime.uniquestream.net/api/v1/series/<content_id>
```

Confirmed live example:

```text
GET /api/v1/series/Yv2I6x71
```

Observed fields:

- `content_id`
- `title`
- `description`
- `images`
- `seasons`
- `episode`
- `audio_locales`
- `subtitle_locales`

Observed image entries:

- `poster_tall`
- `poster_wide`

Observed season fields:

- `content_id`
- `title`
- `season_number`
- `season_seq_number`
- `display_number`
- `episode_count`
- `mal_id`

Observed entry episode fields:

- `content_id`
- `title`
- `image`
- `season_number`
- `season_display`
- `episode_number`
- `duration_ms`
- `episode`
- `is_clip`

Observed locale fields:

- `audio_locales` example: `["ja-JP"]`
- `subtitle_locales` example:
  `["de-DE","en-US","es-419","es-ES","it-IT","ar-SA","pt-BR"]`

Implementation relevance:

- series detail is sufficient to enumerate seasons
- AniBridge can derive locale support without touching the player first
- `mal_id` could become a useful secondary metadata hook later

### 5.4.4 Season episodes

This endpoint was discovered from a Nuxt route chunk and then validated live.

Confirmed endpoint:

```text
GET https://anime.uniquestream.net/api/v1/season/<season_content_id>/episodes?page=<page>&limit=<limit>&order_by=<asc|desc>
```

Confirmed live example:

```text
GET /api/v1/season/kbCNPRyx/episodes?page=1&limit=5&order_by=asc
```

Observed response shape:

- plain JSON array

Observed episode fields:

- `title`
- `episode`
- `is_clip`
- `content_id`
- `episode_number`
- `duration_ms`
- `image`
- `image_loading`

Implementation relevance:

- this endpoint is the key to episode listing
- AniBridge can map season/episode numbers without HTML scraping
- this likely replaces a large part of the AniWorld-style title/episode parser

### 5.4.5 Episode media

User-supplied and confirmed patterns:

```text
GET /api/v1/episode/<content_id>/media/dash/<locale>
GET /api/v1/episode/<content_id>/media/hls/<locale>
```

Confirmed live examples:

```text
GET /api/v1/episode/4LPXo29x/media/dash/de-DE
GET /api/v1/episode/hGOX9ETE/media/hls/de-DE
```

Observed response fields:

- `title`
- `content_id`
- `media_id`
- `dash`
- `hls`
- `versions`
- `has_local`

Observed `hls` fields:

- `locale`
- `playlist`
- `subtitles`
- `hard_subs`

Important observation:

- the `dash` endpoint can still return `dash: null` while including a usable HLS
  payload
- therefore the endpoint naming cannot be treated as a guarantee of transport
  format

Observed HLS behavior:

- base playlist points to signed `mediacache.cc` `master.m3u8` URLs
- `hard_subs` can expose alternate playlists keyed by locale

Implementation relevance:

- AniBridge can likely resolve direct playable URLs without downstream provider
  host scraping
- playback probing should prefer HLS
- DASH support should be treated as optional unless validated title by title

### 5.4.6 Movie media

Confirmed endpoint pattern:

```text
GET /api/v1/movie/<content_id>/media/hls/<locale>
GET /api/v1/movie/<content_id>/media/dash/<locale>
```

Confirmed live example:

```text
GET /api/v1/movie/qCWaP9hW/media/hls/de-DE
```

Observed response shape mirrors episode media.

Implementation relevance:

- the anime site can cover anime movies as well as episodic series
- the same client can likely support both kinds with a small dispatch layer

### 5.4.7 Queue endpoint

Discovered in frontend bundle:

```text
POST /api/v1/queue/<kind>/<protocol>/<content_id>/<locale>
```

Observed from watch page bundle logic:

- used when media is not yet ready
- likely associated with flags such as `hls_not_ready` or `dash_not_ready`

What is confirmed:

- the frontend knows about this route
- it is part of the official client behavior

What is not yet confirmed:

- request body requirements
- response shape
- how often AniBridge would need it

Implementation recommendation:

- do not depend on queueing for phase 1
- implement it only if real-world titles frequently return a not-ready state

## 5.5 Anime site route map discovered from frontend

Observed route patterns include:

- `/search`
- `/videos/new`
- `/videos/movies`
- `/videos/popular`
- `/videos/alphabetical`
- `/videos/:category`
- `/videos/:category/:subcat`
- `/series/:series_id/:title`
- `/watch/:content_id/:title?`

Implementation relevance:

- the frontend route model matches the API object model cleanly
- AniBridge can remain API-first and ignore the rendered route layer except for
  debugging

## 5.6 Anime site implementation feasibility

Feasibility: high

Why:

- search is first-class
- season listing is first-class
- media resolution is first-class
- responses are JSON-native
- no downstream host-page scraping has yet been required

Main unknowns:

- exact semantics of `versions`
- fallback behavior when media is not ready
- whether signed media URLs require special headers or tight freshness windows

None of those unknowns block a first implementation.

## 6. `uniquestream.net` Deep Analysis

## 6.1 Stack and runtime characteristics

Confirmed from page behavior and assets:

- WordPress-backed
- server-rendered HTML pages
- custom front-end player logic
- Cloudflare in front
- per-page JS config object named `uniquestreamPlayer`
- player loading through `wp-admin/admin-ajax.php`

This is not the same platform as the anime site.

## 6.2 Public availability and Cloudflare behavior

Observed behavior:

- some requests without a browser-like user agent returned `403`
- browser-like user agent requests succeeded

Implementation relevance:

- AniBridge should assume this provider may require browser-like headers
- this is still lighter than a full browser automation dependency, but stronger
  than the anime site

## 6.3 WordPress REST behavior

Observed:

- `GET /wp-json/` returns a `403 rest_disabled`
- `GET /?rest_route=/` also returns disabled

However:

- item-specific REST endpoints work
- collection endpoints work

This is a very important distinction.

The REST index is disabled, not the entire REST surface.

## 6.4 Confirmed working WordPress REST collection endpoints

Validated examples:

```text
GET /wp-json/wp/v2/movies?search=avatar&per_page=3
GET /wp-json/wp/v2/tvshows?search=agent&per_page=3
GET /wp-json/wp/v2/episodes/41022
GET /wp-json/wp/v2/movies/40822
GET /wp-json/wp/v2/tvshows/41020
```

Important implication:

- AniBridge can likely use REST endpoints for title search and content lookup
- HTML scraping is not required for the first phase of catalog discovery

This materially improves feasibility.

## 6.5 Main-site movie object model

Confirmed item endpoint:

```text
GET /wp-json/wp/v2/movies/<post_id>
```

Observed fields include:

- `id`
- `slug`
- `status`
- `type`
- `link`
- `title.rendered`
- `content.rendered`
- `excerpt.rendered`
- `meta`
- taxonomy ids like:
  - `genres`
  - `cast`
  - `directors`
  - `writers`
  - `producers`
  - `studios`
  - `countries`
  - `years`

Important caution:

- many `meta` fields appeared zeroed or empty in sampled content
- therefore post meta should not be assumed complete or trustworthy

## 6.6 Main-site TV show object model

Confirmed item endpoint:

```text
GET /wp-json/wp/v2/tvshows/<post_id>
```

Observed fields include:

- `id`
- `slug`
- `link`
- `title.rendered`
- `content.rendered`
- taxonomy ids
- `meta`

Again, sampled `meta` fields such as episode and season counts were often zero.

Conclusion:

- use the REST surface for identity and discovery
- do not rely on metadata completeness

## 6.7 Episode pages and episode objects

Observed on TV show HTML pages:

- direct links to episode permalinks such as:
  - `/episodes/agent-from-above-2026-season-1-episode-1/`

Confirmed item endpoint:

```text
GET /wp-json/wp/v2/episodes/<post_id>
```

Observed fields include:

- `id`
- `slug`
- `link`
- `title.rendered`
- `content.rendered`
- `meta`

Important limitation:

- sampled episode `meta.season_number` and `meta.episode_number` were zero
- therefore season and episode numbering may need to be parsed from:
  - permalink
  - title
  - parent HTML page

This is a known weakness compared with the anime site.

## 6.8 Main-site page-level player config

Confirmed inline object from both movie and episode pages:

```json
{
  "ajaxUrl": "https://uniquestream.net/wp-admin/admin-ajax.php",
  "restUrl": "https://uniquestream.net/wp-json/uniquestream/v1/",
  "restNonce": "d6c0c22199",
  "nonce": "9c09d5d9af",
  "reportNonce": "431962cc04",
  "isLoggedIn": "",
  "userFeaturesNonce": "6a07883515",
  "postId": "41022",
  "captcha": {
    "enabled": true,
    "type": "turnstile",
    "turnstileSiteKey": "0x4AAAAAAB_Be1ca66EGQu0F"
  },
  "settings": {
    "ajaxEnabled": 1,
    "autoloadEnabled": 0,
    "autoloadDelay": 5
  }
}
```

Important implications:

- the player contract is officially exposed to the browser
- player loading is nonce-gated
- nonces appear page-derived
- the custom REST namespace exists, but the browser player path uses AJAX, not
  that REST base

## 6.9 Main-site player button contract

Confirmed button markup on both movie and episode pages:

```html
<button type="button" class="server-btn"
  data-post="41022"
  data-type="mv"
  data-num="1">
```

Observed fields:

- `data-post`
- `data-type`
- `data-num`

In sampled pages:

- `data-type` was `mv`
- only server slot `1` was observed

## 6.10 Main-site player AJAX contract

Confirmed by inspecting player JS and validating a live request.

Frontend JS performs:

```text
POST https://uniquestream.net/wp-admin/admin-ajax.php
```

with form data:

- `action = uniquestream_player_ajax`
- `nonce = <uniquestreamPlayer.nonce>`
- `post = <data-post>`
- `type = <data-type>`
- `nume = <data-num>`

Confirmed live response:

```json
{
  "embed_url": "<iframe class=\"uniquestream-player-frame\" src=\"//hls.uniquestream.net/local_embed?id=H1hwi922m2axjx9iew28ox\" frameborder=\"0\" scrolling=\"no\" allow=\"autoplay; encrypted-media\" allowfullscreen></iframe>",
  "type": "iframe",
  "msg": ""
}
```

This is the most important main-site confirmation from the entire analysis.

It proves that AniBridge can:

1. fetch a page
2. extract nonce and server metadata
3. call WordPress AJAX
4. obtain an embed iframe

That is not yet the final media URL, but it is a very strong feasibility signal.

## 6.11 Main-site remaining unresolved layer

What is still unresolved:

- what exactly lives behind `//hls.uniquestream.net/local_embed?id=...`
- whether that iframe contains a direct HLS URL, another player abstraction, or
  a transient token exchange
- whether extra anti-bot, referer, or timing checks exist on that layer

This matters because:

- AniBridge ultimately wants a playable media URL or a tractable stream source
- the AJAX response gives an embed container, not yet a final stream

Conclusion:

- the main site is confirmed automatable at least through the embed stage
- final media extraction is still a second-step investigation

## 6.12 Main-site feasibility

Feasibility: medium

Why not high:

- two-step extraction path
- nonce dependence
- Cloudflare sensitivity
- incomplete metadata
- unconfirmed final stream extraction after iframe resolution

Why not low:

- search/listing endpoints are real
- episode permalinks are discoverable
- player AJAX contract is real and verified

## 7. Comparative Assessment

## 7.1 Anime site vs main site

Anime site:

- native JSON API
- direct media endpoint
- clean content IDs
- explicit season/episode data
- lower parsing complexity

Main site:

- REST only partly open
- metadata weaker
- player loading requires page fetch plus nonce
- actual media is at least one more hop away

## 7.2 Fit with AniBridge priorities

AniBridge optimizes for:

- predictable automation
- low-breakage provider logic
- clear title resolution
- stable media probing

Against those priorities:

- `anime.uniquestream.net` is an excellent candidate
- `uniquestream.net` is a viable but fragile candidate

## 8. Recommended Provider Design

## 8.1 Provider naming

Recommended approach:

- add a provider family namespace `uniquestream`
- implement at least two concrete provider/client combinations:
  - `uniquestream_anime`
  - `uniquestream_main`

User-facing naming can be refined later, but the code should preserve the fact
that these are different systems.

## 8.2 Recommended initial scope

Phase 1 should implement only the anime site.

Specifically:

- title search
- series lookup
- season/episode enumeration
- anime movie lookup
- direct HLS media extraction
- probe-quality integration

This gives AniBridge useful support quickly and with low architectural risk.

## 8.3 Shared abstractions worth introducing

If implemented carefully, the following shared abstractions would be useful:

- provider-native search result model
- provider-native content identifier model
- provider-native media result model
- provider-specific direct-stream probe path

Do not introduce a shared abstraction for:

- HTML parser behavior
- WordPress nonce handling
- anime site season content IDs

Those are provider-specific concerns and should remain isolated.

## 9. Proposed Implementation Plan

## 9.1 Phase 1: `anime.uniquestream.net`

Recommended deliverables:

- new provider package:
  - `apps/api/app/providers/uniquestream_anime/`
- native client:
  - search
  - fetch series
  - fetch season episodes
  - fetch movie media
  - fetch episode media
- provider integration:
  - register in `apps/api/app/providers/__init__.py`
  - wire into `apps/api/app/utils/title_resolver.py`
  - wire into `apps/api/app/utils/probe_quality.py`

Recommended behavior:

- prefer `hls` media path
- request locale `de-DE` first, with configurable fallback if needed
- treat `hard_subs` as optional alternate variants
- ignore queue endpoint initially

### 9.1.1 Matching strategy

Search strategy:

1. query `/search`
2. filter by expected content kind where possible
3. score by normalized title and release-year hints
4. prefer exact or near-exact title matches

Episode strategy:

1. resolve series via search
2. fetch series detail
3. find target season from `season_number` or `display_number`
4. fetch season episodes
5. select target episode by `episode_number`
6. fetch media

Movie strategy:

1. resolve movie via search or browse fallback
2. fetch movie media directly

### 9.1.2 Probe-quality integration

AniBridge already treats Megakino specially in
`apps/api/app/utils/probe_quality.py`.

Recommended addition:

- add a direct-probe branch for the anime provider
- do not route anime UniqueStream through AniWorld-style episode/provider logic

## 9.2 Phase 2: optional `uniquestream.net` catalog support

Only start this after phase 1 is stable.

Recommended deliverables:

- native client for:
  - `wp-json/wp/v2/movies`
  - `wp-json/wp/v2/tvshows`
  - `wp-json/wp/v2/episodes`
- HTML fallback helpers for:
  - extracting episode permalinks from TV pages
  - parsing server button metadata if REST data is incomplete

Recommended goals for this phase:

- title search
- show lookup
- episode discovery
- movie lookup

Do not promise final media extraction yet in this phase unless the iframe layer
has also been mapped.

## 9.3 Phase 3: optional `uniquestream.net` playback extraction

This is a distinct milestone.

Required work:

1. fetch title or episode page
2. extract `uniquestreamPlayer`
3. extract `server-btn` metadata
4. call `uniquestream_player_ajax`
5. resolve iframe content
6. determine if direct media URL can be derived reliably

If step 6 depends on unstable browser automation, anti-bot solving, or frequent
token churn, this phase may be intentionally abandoned.

That would still be a success if phase 1 anime support ships cleanly.

## 10. Suggested Code Structure

Recommended layout:

```text
apps/api/app/providers/uniquestream_anime/
  __init__.py
  client.py
  provider.py
  models.py

apps/api/app/providers/uniquestream_main/
  __init__.py
  client.py
  provider.py
  models.py
```

Optional shared helpers if they prove useful:

```text
apps/api/app/providers/uniquestream_common/
  __init__.py
  matching.py
  normalization.py
```

Recommendation:

- do not create `uniquestream_common` until duplicate logic actually exists

## 11. Data Model Recommendations

## 11.1 Anime client internal models

Useful internal models:

- `UniqueStreamAnimeSearchResult`
- `UniqueStreamAnimeSeries`
- `UniqueStreamAnimeSeason`
- `UniqueStreamAnimeEpisode`
- `UniqueStreamAnimeMedia`
- `UniqueStreamAnimeHardSubVariant`

Useful fields:

- `content_id`
- `title`
- `kind`
- `season_number`
- `episode_number`
- `duration_ms`
- `image`
- `audio_locales`
- `subtitle_locales`
- `playlist_url`
- `hard_sub_variants`

## 11.2 Main-site client internal models

Useful internal models:

- `UniqueStreamMainPost`
- `UniqueStreamMainShow`
- `UniqueStreamMainEpisode`
- `UniqueStreamMainPlayerBootstrap`
- `UniqueStreamMainEmbedResult`

Useful fields:

- `post_id`
- `slug`
- `link`
- `title`
- `kind`
- `season_number`
- `episode_number`
- `nonce`
- `player_type`
- `player_num`
- `embed_url`

## 12. Risk Analysis

## 12.1 Anime-site risks

Low-to-medium risk items:

- signed media URLs may expire quickly
- locale semantics may not exactly match audio language expectations
- `dash` endpoint naming is misleading and should not be assumed reliable
- queueing behavior is not fully mapped

Overall risk level: low

## 12.2 Main-site risks

Medium-to-high risk items:

- Cloudflare can change request acceptance behavior
- page nonces may become shorter-lived or harder to extract
- player AJAX could add referer or cookie checks
- iframe resolution could become the real hard part
- WordPress REST availability could be narrowed without warning
- incomplete metadata may require more HTML parsing than expected

Overall risk level: medium-high

## 12.3 Product risk of doing both at once

High.

Why:

- different backends
- different failure modes
- different extraction paths
- different test matrices

Recommendation:

- explicitly avoid bundling both into one implementation milestone

## 13. Testing Strategy

## 13.1 Unit tests

For anime site:

- search response parsing
- series parsing
- season episode parsing
- media parsing
- locale fallback behavior
- title matching and scoring

For main site:

- REST parsing
- permalink season/episode extraction
- `uniquestreamPlayer` JSON extraction
- `server-btn` extraction
- AJAX response parsing

## 13.2 Integration tests

Anime:

- search a known title
- resolve a known season/episode
- fetch media
- verify HLS URL shape

Main site:

- search movie by REST
- search TV show by REST
- fetch episode page
- extract nonce
- call player AJAX
- verify embed URL shape

## 13.3 Drift detection

Recommended for both providers:

- record representative fixtures from live responses
- keep parser tests against those fixtures
- add structured logging around parse failures

This is especially important for the main site.

## 14. Operational Recommendations

## 14.1 Logging

Recommended debug fields:

- provider name
- query
- matched content id or post id
- season number
- episode number
- selected locale
- media endpoint used
- player AJAX step reached
- iframe URL host

## 14.2 Error classification

Recommended error buckets:

- title not found
- season not found
- episode not found
- media unavailable
- provider response malformed
- provider challenge or access denied
- embed extraction failed
- final stream extraction failed

The separation matters because the main site will fail differently from the
anime site.

## 15. Implementation Checklist

### Phase 1: anime provider

- add `uniquestream_anime` client package
- implement search endpoint wrapper
- implement series endpoint wrapper
- implement season-episodes wrapper
- implement movie media wrapper
- implement episode media wrapper
- add provider registration
- extend title resolution
- extend quality probing
- add parser and integration tests
- document provider behavior

### Phase 2: main-site discovery provider

- add `uniquestream_main` client package
- implement movie REST search
- implement TV REST search
- implement episode REST fetch
- implement HTML episode link extraction
- add search and parsing tests

### Phase 3: main-site playback provider

- implement page bootstrap extraction
- implement `server-btn` extraction
- implement `uniquestream_player_ajax` request
- inspect iframe layer
- decide whether final stream extraction is stable enough to keep

## 16. Recommended Decision

AniBridge should proceed with `anime.uniquestream.net` support now and should
not block that work on the much noisier `uniquestream.net` integration.

Recommended product decision:

- official first milestone: anime UniqueStream support
- explicit follow-up investigation: main-site catalog and playback extraction
- no promise yet that the main site will reach production quality

This is the highest-confidence path to shipping useful UniqueStream support
without polluting the provider architecture with premature generalization.

## 17. Final Assessment

If the goal is "add UniqueStream support" in the most practical sense, the
anime site already gives AniBridge a strong and efficient entry point.

If the goal is "fully support everything under UniqueStream", the work should be
treated as two separate integrations:

- one straightforward
- one exploratory

That distinction should drive the implementation plan, the tests, and the
expectations set in the codebase.
