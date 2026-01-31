# Major Issue: S.to "Version 2" migration risks (AniWorld likely affected)
---
post_title: "S.to Version 2 Migration Risks"
author1: "Zzackllack"
post_slug: "sto-v2-migration-risks"
microsoft_alias: "tbd"
featured_image: ""
categories:
  - "specs"
tags:
  - "s.to"
  - "aniworld"
  - "migration"
  - "risk"
ai_note: "Drafted with AI assistance."
summary: "Issue tracking notes for the S.to v2 migration and AniBridge impact."
post_date: "2026-01-31"
title: "Major Issue: S.to Version 2 migration risks"
status: "open"
created_by: "Zzackllack"
created_at: "2026-01-18 22:35:36.000 UTC"
---

## Major Issue: S.to "Version 2" migration risks

### Context

S.to (Serienstream) published a shutdown notice clarifying the current platform will be archived and replaced by a new Version 2 site. The announcement emphasizes a new website structure, new design, and many functional changes. This directly threatens AniBridge provider integrations because our catalog and search extraction relies on the existing S.to/AniWorld structure and catalog URLs.

Primary source: [S.to shutdown notice](https://s.to/sto-wird-dauerhaft-abgeschaltet-2026)

### Key points from the announcement (interpreted)

- The existing S.to system is being permanently retired soon, with many parts already outdated or unreliable (notably search).
- User behavior shifted to mobile, and the current technical stack is considered obsolete.
- A full migration to a new platform is underway; the new site will go online soon.
- The new site promises a similar structure but a new design and many new features.
- The migration will take multiple days as data is reformatted and processes are reworked.
- S.to itself will remain available; the shutdown refers to the old system.

### Impact on AniBridge (high risk)

- **Catalog endpoints are fragile**: AniBridge indexes S.to via `s.to/serien` and AniWorld via `aniworld.to/animes`. Any URL or DOM changes break discovery of new titles.
- **Search behavior already changed**: S.to notes their search function behavior has changed; our search parsing may already be degraded or inconsistent.
- **AniWorld likely shares the same platform**: Design parity suggests a shared backend or theme, so S.to changes can cascade to AniWorld and vice versa.
- **Provider parsing likely to break**: A new design + structure implies broken selectors for listings, detail pages, and player/hoster selection.
- **Third-party dependency risk**: AniBridge relies on the `aniworld` Python package from the community [AniWorld-Downloader](https://github.com/phoenixthrush/AniWorld-Downloader). This means provider breakage may be gated by upstream changes; we might need to contribute patches, maintain a fork, or selectively re-implement critical parsing paths (catalog listing, search, episode/hoster extraction) in-house to avoid blocking releases.

### Why this is urgent

- AniBridge cannot index or discover new series/episodes without catalog URLs.
- A broken catalog means no new releases for Prowlarr/Sonarr automation.
- If both S.to and AniWorld migrate in tandem, a single refactor could be required across multiple providers at once.

### Opportunities created by the migration

- **Upgrade indexing strategy**: Move away from fragile DOM scraping and introduce a catalog fetcher that tolerates URL changes (sitemap parsing, JSON data feeds, or structured data extraction if exposed).
- **Introduce an internal catalog cache**: Store provider series/episode metadata in DB and refresh in background to avoid hard dependency on live catalog pages.
- **Integrate recommendations metadata**: The new S.to platform emphasizes recommendations, collections, and dynamic discovery. If exposed, we could enrich Torznab results with smarter ordering or “recommended” tags.
- **Consider Web UI**: The repo already lists a "Toggleable WebUI" as planned. This migration could provide design cues or functional inspiration for discovery, catalogs, and recommended series flows.
- **Multi-provider abstraction**: Treat AniWorld/S.to as a shared provider family and implement a versioned adapter that can be switched per provider without touching core logic.

### Proposed tasks (high level)

1. Monitor S.to and AniWorld catalog URLs daily and alert on unexpected HTML or status changes.
2. Capture before/after HTML snapshots of `s.to/serien` and `aniworld.to/animes` when Version 2 launches.
3. Identify new catalog endpoints (sitemap, JSON, or structured HTML lists) and adjust title discovery logic.
4. Harden search: detect if in-page search is replaced by API calls; add fallbacks.
5. Add provider capability flags (v1/v2) to allow gradual migration.
6. Plan a future Web UI spike to leverage new discovery signals (recommendations, collections).

### References

- Announcement: [S.to shutdown notice](https://s.to/sto-wird-dauerhaft-abgeschaltet-2026)
- Upstream dependency: [AniWorld-Downloader](https://github.com/phoenixthrush/AniWorld-Downloader)
- Current catalog URLs:
  - S.to: [S.to series list](https://s.to/serien)
  - AniWorld: [AniWorld catalog](https://aniworld.to/animes)

### Acceptance criteria

- AniBridge can still discover and index new titles after S.to Version 2 launch.
- AniWorld indexing remains functional or is updated in lockstep.
- Catalog discovery does not depend on a single brittle page structure.
- A documented mitigation path exists for future provider redesigns.

---

### Comment by @Zzackllack at 2026-01-29 22:12:02.000 UTC

They migrated to version 2.

---

### Comment by @Zzackllack at 2026-01-29 22:30:59.000 UTC

Non-public API under [S.to API](https://s.to/api/) for instance search with `?term=` like [search suggest](https://s.to/api/search/suggest?term=9-1-1)

---


### Comment by @Zzackllack at 2026-01-29 23:05:49.000 UTC

Findings:

```javascript
http://s.to/api/text-templates/search?q=12324
https://s.to/api/collections/for-series/
, j = "episode" === m ? "/api/episodes/".concat(e, "/comments") : "/api/series/".concat(t, "/comments");
const {data: n} = await l.get("/api/content-adjustments/".concat(e, "/").concat(t, "/data"));

      `await l.post("/api/content-adjustments", o, {
                                headers: {
                                    "X-CSRF-TOKEN": a,
                                    "Content-Type": "multipart/form-data"
                                }
                            }),

            const n = await fetch("/api/collections/for-series/".concat(e), {
                credentials: "same-origin"
            })

/api/collections/my?term=
/api/collections/for-series/
/api/collections/attach
```

---

### Comment by @Zzackllack at 2026-01-30 21:43:54.000 UTC

Catalog/Series list now available under [S.to alpha catalog](https://s.to/serien?by=alpha)

---
