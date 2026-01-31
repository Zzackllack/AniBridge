---
post_title: "S.to V2 Recovery - Findings and Plan"
author1: "Zzackllack"
post_slug: "sto-v2-recovery-findings-plan"
microsoft_alias: "tbd"
featured_image: ""
categories:
  - "specs"
tags:
  - "s.to"
  - "aniworld"
  - "v2"
  - "catalog"
  - "parsing"
ai_note: "Drafted with AI assistance."
summary: "Research findings and implementation options for restoring S.to v2 support."
post_date: "2026-01-31"
---

## S.to V2 Recovery - Findings and Plan

## Scope and intent

This document captures a deep-dive analysis of the S.to v2 migration and proposes multiple implementation approaches to restore AniBridge behavior (catalog discovery, search, episode discovery, provider resolution, and downloads). It includes findings from the codebase, the local venv dependency (`aniworld`), and external observation of the live S.to v2 site. No code changes are included here.

## Sources reviewed

- Repo specs and incident notes: `specs/007-sto-v2-support/github-issue.md`
- Existing S.to integration spec: `specs/003-add-sto-support/spec.md`
- V2 catalog HTML snapshot: `specs/007-sto-v2-support/s.to-serien_by=alpha.html`
- AniBridge implementation files:
  - `app/providers/sto/provider.py`
  - `app/utils/title_resolver.py`
  - `app/config.py`
  - `app/core/downloader/episode.py`
  - `app/core/downloader/provider_resolution.py`
  - `app/core/downloader/download.py`
  - `app/providers/megakino/client.py`
- Local dependency (venv): `.venv/lib/python3.12/site-packages/aniworld/*`
- External live site checks (public endpoints):
  - `https://s.to/serien?by=alpha`
  - `https://s.to/serie/9-1-1`
  - `https://s.to/serie/9-1-1/staffel-1/episode-1`
  - `https://s.to/api/search/suggest?term=9-1-1`
  - `https://s.to/robots.txt`
- Context7 docs used: Playwright Python (network interception patterns)

## Executive summary (what changed)

- S.to v2 no longer exposes the v1 URL structure that AniBridge and AniWorld-Downloader expect.
- Catalog listing and series pages are now plain `/serie/<slug>` (no `/serie/stream/<slug>`).
- Episode pages embed provider and language data directly in HTML via data attributes and a tokenized `/r?t=...` play URL.
- There is a public, non-auth API for search suggestions at `/api/search/suggest`.
- Several internal APIs exist but require CSRF and likely session cookies; these are currently not reliable for anonymous scraping.

## Detailed findings

### 1) Catalog and series discovery (v2)

Observed from `https://s.to/serien?by=alpha` and HTML snapshot in `specs/007-sto-v2-support/s.to-serien_by=alpha.html`:

- Catalog page is live and lists all series with anchors of the form:
  - `/serie/<slug>`
- Alphabet navigation is now:
  - `/katalog/A` ... `/katalog/Z` and `/katalog/0-9`
- The query parameter `by=alpha` is active; `by=genre` exists as alternate sorting.

Implications for AniBridge:

- The configured `STO_ALPHABET_URL` still defaults to `/serien-alphabet` (v1), which is now obsolete.
- Slug extraction regex for s.to (`/serie/stream/<slug>`) must be updated to `/serie/<slug>`.

### 2) Series pages (v2)

Observed from `https://s.to/serie/9-1-1`:

- Season links are `/serie/<slug>/staffel-<n>`.
- Episode links are `/serie/<slug>/staffel-<n>/episode-<m>`.
- The HTML contains enough structure to extract a season list and episode URLs without executing JS.

### 3) Episode pages (v2) and provider data

Observed from `https://s.to/serie/9-1-1/staffel-1/episode-1`:

- The provider list is embedded directly in the HTML as buttons with data attributes:
  - `data-play-url="/r?t=<token>"` (opaque tokenized URL)
  - `data-provider-name="VOE" | "Doodstream" | ...`
  - `data-language-label="Deutsch" | "Englisch"`
  - `data-language-id="1" | "2"` (numeric language key)
  - `data-link-id="<numeric>"`
- The same `/r?t=...` token appears in the main player iframe `src`.
- `window.__reactMountQueue` includes `seriesId` and `episodeId` in JSON props for the comments widget.
- CSRF token is embedded in a `<meta name="csrf-token">` element.

Implications for AniBridge:

- S.to v2 no longer uses the v1 `li.episodeLink` structure or `/redirect/` URLs.
- AniBridge can directly parse provider candidates and language mapping from HTML.
- `/r?t=...` must be followed to obtain the provider embed URL; treat as opaque and do not attempt to decode.

### 4) Language handling (v2)
Episode pages expose language per provider via data attributes and visible headings (e.g., "Deutsch", "Englisch"). Recommended handling:

- Treat each provider button as a distinct candidate with language metadata.
- Extract and store:
  - `data-language-id` (numeric key)
  - `data-language-label` (localized display label)
  - `data-provider-name`
  - `data-play-url`
- Normalize to internal language codes using a simple mapping:
  - `1` -> `de` (German)
  - `2` -> `en` (English)
- If `data-language-id` is missing, fall back to `data-language-label` string matching.
- Preserve both raw `language_id` and `language_label` for debugging and future additions.
- Resolution preference should filter by language order (e.g., `de` then `en`), with a final fallback to any available language.

### 5) Public API endpoints (v2)

Observed from live site and JS bundles:

- `GET /api/search/suggest?term=...`
  - Returns JSON with `shows[]`, each containing a `name` and a `url` (relative `/serie/<slug>`).
  - Works without auth.

### 6) Private or CSRF-gated endpoints (v2)

Observed from JS bundles and HTML:

- `POST /api/episodes/watched`
  - Payload (episode page): `{series_id, season_no, episode_no, episode_id, seen}`
  - Payload (series page toggle): `{series_id, season_no, episode_no, episode_id, toggle: true}`
  - Requires `X-CSRF-TOKEN` header and likely session cookies.
- Bulk season marking (series page):
  - Script targets `#season-mark` and reads `data-mark-url`.
  - Sends `POST` JSON `{ action: "seen" | "unseen" }` to `data-mark-url` with CSRF + `X-Requested-With: XMLHttpRequest`.
  - Markup was not present in the guest HTML export (likely auth-only).
- `GET /api/collections/my?term=...`
- `GET /api/collections/for-series/<id>`
- `POST /api/collections/attach`
- `GET /api/text-templates/search?q=...`
- Mentioned in issue notes (likely auth required):
  - `/api/episodes/<id>/comments`
  - `/api/series/<id>/comments`
  - `/api/content-adjustments/<id>/<type>/data`

Observations:

- Attempting `https://s.to/api/collections/for-series/3592` without auth returns an HTML login page.
- `https://s.to/api/episodes/157141/comments` returned 500 without auth.
- Series page scripts reference `.episode-eye` buttons with data attributes (`data-series-id`, `data-season-no`, `data-episode-no`, `data-episode-id`). These elements were not present in the guest export, indicating they may be rendered only when logged in.

Implications:

- These endpoints are likely not reliable for anonymous scraping.
- Use them only if we introduce session handling (cookie + CSRF + optional login).

### 7) Robots and sitemap

- `https://s.to/robots.txt` advertises `Sitemap: /sitemap.xml`.
- `https://s.to/sitemap.xml` currently returns 404.

Implications:

- Sitemap ingestion is not currently available; fallback to HTML catalog is required.

## AniBridge-specific impact analysis

### Current s.to integration (AniBridge)

- Provider config:
  - `STO_ALPHABET_URL` default: `/serien-alphabet` (v1)
  - Slug regex for s.to: `/serie/stream/<slug>`
- Index building parses anchors and uses slug extraction regexes in `app/utils/title_resolver.py`.

Breakage points:

- Catalog URL is wrong for v2.
- Slug extraction misses v2 URLs.
- Download paths assume aniworld `Episode` semantics and v1 URLs.

### AniWorld-Downloader dependency status

Findings from `.venv/lib/python3.14/site-packages/aniworld/*`:

- `aniworld/config.py` hardcodes:
  - `S_TO = "http://186.2.175.5"`
  - `SUPPORTED_SITES["s.to"]` with `stream_path = "serie/stream"`
- `aniworld/models.py`:
  - Episode provider extraction assumes `li.episodeLink` and `/redirect/...` paths.
- `aniworld/search.py` uses only AniWorld endpoints (`/ajax/seriesSearch`).

Implications:

- AniWorld-Downloader can still provide provider extractors (VOE, Doodstream, etc.), but its S.to site parsing is v1-only.
- For S.to v2 we should bypass aniworld’s site parsing and only reuse its provider extractors where possible.

## Multi-approach implementation options

### Approach A: HTML-only scraping

Description:

- Parse catalog from `https://s.to/serien?by=alpha` and `/katalog/<letter>`.
- Parse series pages for season and episode URLs.
- Parse episode pages for provider buttons and `data-play-url` tokens.
- Follow `/r?t=...` to provider embed, then use extractors or yt-dlp.

Pros:

- No auth or CSRF dependency.
- Works without JS execution.
- Fast to implement.

Cons:

- HTML structure changes can break parsing.
- Requires careful selector maintenance.

Rating (1-5):

- Reliability: 3
- Complexity: 3
- Speed to ship: 4
- Maintainability: 3
- Risk of block/lockout: 2

### Approach B: API-first reverse engineering

Description:

- Use Playwright to capture network calls and identify stable v2 JSON endpoints.
- Build a pure API client for catalog, series, episodes, and provider links.

Pros:

- Structured data; less DOM brittleness.
- Potentially richer metadata (collections, recommendations).

Cons:

- Requires session handling and CSRF token management.
- Higher maintenance and operational complexity.

Rating (1-5):

- Reliability: 4 (if stable)
- Complexity: 5
- Speed to ship: 2
- Maintainability: 4
- Risk of block/lockout: 4

### Approach C: Upstream AniWorld-Downloader fork

Description:

- Patch upstream dependency to support v2 URLs and HTML structure.
- Keep AniBridge aligned with upstream behavior via fork.

Pros:

- Keeps logic centralized and reusable.
- Reuses extractor ecosystem.

Cons:

- Fork maintenance burden.
- Still requires v2 parsing work.

Rating (1-5):

- Reliability: 3
- Complexity: 4
- Speed to ship: 3
- Maintainability: 2
- Risk of block/lockout: 2

### Approach D: Hybrid (Recommended)

Description:

- HTML for catalog + series/episode discovery.
- Use `/api/search/suggest` for fast lookup.
- Parse episode HTML for provider data and `/r?t=...` tokens.
- Use provider extractors from aniworld or yt-dlp as fallback.
- Keep Playwright only as diagnostic tooling for future API discovery.

Pros:

- No auth dependency.
- Fast to restore core behavior.
- Keeps existing extractor investment.

Cons:

- Still coupled to HTML for episodes.
- API-only features (comments/collections) remain unused.

Rating (1-5):

- Reliability: 4
- Complexity: 3
- Speed to ship: 5
- Maintainability: 4
- Risk of block/lockout: 2

## Recommended path (Hybrid)

1. **Catalog recovery**
   - Update s.to alphabet URL to `https://s.to/serien?by=alpha`.
   - Update s.to slug regex to match `/serie/<slug>`.
2. **Search recovery**
   - Add `/api/search/suggest?term=` as fast search fallback.
3. **Episode discovery**
   - Parse season/episode links from series page HTML.
4. **Provider resolution**
   - Parse provider buttons on episode page and extract `data-play-url`, `data-provider-name`, `data-language-id`.
   - Follow `/r?t=...` to provider embed URL.
   - Reuse aniworld provider extractors for direct link resolution.
5. **Resilience**
   - DOM contract tests to detect HTML changes early.
   - Add a small diagnostic Playwright harness for future v2 API mapping.

## Implementation plan (phased)

### Phase 0 - Safety and instrumentation

- Add a small diagnostic mode (no production usage) to record HTML/endpoint failures.
- Log when s.to parsing fails, including URL and selector.
- Cache last-known-good catalog to avoid total outages.

### Phase 1 - Catalog and slug parsing

- Update s.to alphabet URL in config.
- Update s.to slug regex in `app/utils/title_resolver.py`.
- Adjust index parsing if needed to avoid missing titles.

### Phase 2 - Episode parsing and provider extraction

- Implement v2 episode parsing using `data-play-url` and provider data.
- Follow `/r?t=...` redirect to provider embed URL.
- Use existing provider extractors and fallback to yt-dlp if extractors fail.

### Phase 3 - Search fallback

- Integrate `/api/search/suggest?term=` as a search hint.
- Merge results with catalog index and existing title resolution.

### Phase 4 - Validation and monitoring

- Add lightweight contract tests (catalog URL, series page, episode page selectors).
- Monitor for structural changes in v2 HTML.
- Document fallback strategy in release notes.

## Risks and mitigations

- **HTML changes**: Use stable attributes (`data-play-url`, `data-provider-name`) rather than class names. Add contract tests.
- **Redirect token changes**: Treat `/r?t=...` as opaque and only follow redirect.
- **Provider extractor drift**: Isolate extractor usage and add fallback to yt-dlp.
- **Auth-gated APIs**: Use only public `search/suggest` without auth; keep API-first approach as optional future work.

## Decision log

- Primary approach chosen: Hybrid (HTML + public API + provider extractors).
- API-first approach is deferred due to auth/CSRF complexity.
- AniWorld-Downloader is kept only for provider extractors; v2 parsing is handled in AniBridge.

## Open questions

- Do we want to build a login-capable API client to access collections or comments?
- Should we add a persistent catalog cache table to reduce live scraping?
- Should AniWorld v2 be proactively tested, assuming the same platform?

## Appendix: concrete endpoint samples

### Search suggest

```json
GET https://s.to/api/search/suggest?term=9-1-1
{
  "shows": [
    {"name": "9-1-1", "url": "/serie/9-1-1"},
    {"name": "9-1-1: Lone Star", "url": "/serie/9-1-1-lone-star"}
  ],
  "people": [],
  "genres": []
}
```

### Episode watched (CSRF/session required)

```json
POST https://s.to/api/episodes/watched
Headers:
  X-CSRF-TOKEN: <meta csrf-token>
  X-Requested-With: XMLHttpRequest
Body:
  {
    "series_id": 3592,
    "season_no": 1,
    "episode_no": 1,
    "episode_id": 157141,
    "seen": true
  }
```

### Provider data (HTML attributes)

```html
<button
  data-link-id="21649813"
  data-play-url="/r?t=..."
  data-provider-name="VOE"
  data-language-label="Deutsch"
  data-language-id="1"
>
```
