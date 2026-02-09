# 012 Specials/Extras via Sonarr - Recommended Design

## Design goals

- Return episode-specific results for specials searched by title.
- Preserve compatibility with Sonarr request behavior (`search` then `tvsearch`).
- Decouple AniWorld film ordering from Sonarr episode numbering.
- Keep download resolver accurate (real AniWorld target) while making release naming mappable by Sonarr.

## Architecture changes

### 1) Add AniWorld specials catalog parser

Create a parser service (e.g. `app/providers/aniworld/specials.py`) that:

- fetches/caches `/anime/stream/{slug}/filme`,
- parses rows in `#season0` into:
  - `film_index` (from `film-N` URL),
  - `episode_id` (`data-episode-id`),
  - `episode_season_id` (`data-episode-season-id`),
  - `title_de` (`<strong>`),
  - `title_alt` (`<span>`),
  - tags inferred from text: `OVA`, `Movie`, `Part`, `Special`.

### 2) Add title matcher for special queries

Implement a scorer for `t=search` queries:

- normalize punctuation/whitespace/unicode apostrophes,
- score token overlap + phrase contains + `part n` exact bonus,
- include both DE and EN/alt title tokens,
- require confidence threshold to avoid false positives.

### 3) Update Torznab `t=search` flow

Current behavior returns generic preview (S01E01 probe) for all text queries.

Change:

- after slug resolution, attempt special-title matching against AniWorld specials catalog.
- on confident match:
  - probe actual AniWorld target (`season=0`, `episode=film_index`),
  - emit targeted RSS items only for matched special (and languages),
  - include `SxxEyy` in release title (do not omit).
- on no confident match: keep current preview fallback.

### 4) Update Torznab `t=tvsearch` fallback behavior

When direct probe for requested `season/ep` yields no available items:

- if site is AniWorld and specials catalog exists:
  - try mapping to specials entry.

Mapping strategy order:

1. Metadata-backed mapping (when identifiers available and enabled).
2. Query-title assisted mapping (if request context has a recent special title candidate).
3. Conservative fallback: no synthetic mapping (avoid wrong releases).

### 5) Release naming and magnet metadata strategy

For matched specials:

- magnet metadata should always keep real AniWorld target (`aw_s=0`, `aw_e=film_index`).
- release title should use Sonarr-facing alias numbering when available (requested `season/ep` context).

Rationale:

- Sonarr parser uses release title conventions for matching.
- Download resolver still reaches correct AniWorld special page.

### 6) Torznab capability expansion for IDs

Expand supported tv-search params in caps to include:

- `tvdbid`, `imdbid`, `rid`, `tvmazeid`, `tmdbid` (in addition to `q,season,ep`).

Also parse these optional query params in API handler and carry them in matching context.

Benefit:

- enables Sonarr to send deterministic IDs when available,
- unlocks metadata-backed matching.

### 7) Metadata-backed resolver (phase 2)

Add optional resolver module (feature-flagged):

- input: `(tvdbid|tmdbid|...) + season + ep` OR special title,
- output: canonical episode title(s) for matching against AniWorld specials catalog.

Do not hard-fail search when metadata lookup fails. Fallback to heuristic mode.

## Data model additions (lightweight)

- `SpecialEntry` (in-memory dataclass).
- optional persistent cache table for specials parse snapshots (slug/site/updated_at/payload hash) if repeated live scraping becomes expensive.

## Failure modes and guardrails

- Low-confidence match: return no special-targeted item; use existing fallback behavior.
- Multiple near-equal matches: return none unless one clearly wins; avoid false positives.
- Missing `/filme` page: keep existing flow.

## Compatibility

- No breaking change for non-special searches.
- Existing season-zero handling remains valid.
- STRM mode should use same mapped release naming logic.
