# [FEATURE] STRM dead-link refresh scaffolding

**State:** open
**Created by:** @Zzackllack
**Created at:** 2025-12-21 00:41:01.000 UTC

## Summary

Add scaffolding to persist STRM-to-resolved-URL mappings so AniBridge can later refresh expired provider URLs without changing current runtime behavior.

## Further Information

See the spec notes for context: `specs/004-strm-file-support/refresh-boilerplate.md`

## Problem

STRM files currently store resolved provider URLs that can expire (tokens/TTL/geo constraints). When they expire, playback fails until a new STRM is generated. There is no persisted mapping to support a future refresh endpoint or automation.

## Proposal (Scaffolding Only)

Introduce a new SQLModel table (not yet wired into runtime or migrations) to store:

- `strm_path`
- `resolved_url`
- `resolved_at`
- Episode identity: `slug`, `season`, `episode`, `language`, `site`
- Optional: `provider_used`

Suggested model (do NOT wire into `app/db/models.py` yet unless also handling migrations/runtime table creation):

- `StrmUrlMapping` with a dedicated `id` PK
- `resolved_at` defaults to UTC now

## Suggested Future Write Points (Not Implemented)

- When STRM job finishes writing `.strm`, insert/update mapping row for `strm_path` + episode identity.
- If a future refresh endpoint exists, re-resolve URL, rewrite `.strm`, update mapping row.

## Potential Future Triggers (Not Implemented)

There are lots of possible triggers for refresh:

- A Web UI with a per-episode/per-anime “Refresh STRM” button.
- A CLI command that refreshes a specific episode/season/series.
- An HTTP API endpoint that can be called by automation.
- Some “refresh all” or “refresh stale” action tied to UI or CLI.

## Suggested Future “Dead Link” Detection (Not Implemented)

- Simple: HEAD/GET and mark dead on 4xx/5xx/timeouts.
- Better: retry window; treat 403/451/429 differently.
- Consider proxy/VPN: failures may be geo/rate-limit, not expiry.

## Notes (Sonarr Sorting Context)

- Sonarr ranks releases using size/quality/profiles, not STRM semantics.
- STRM entries currently use the same enclosure length heuristic as non-STRM to avoid rejection by minimum size rules.
- Titles keep quality tags and add `[STRM]`.

## Acceptance Criteria

- Document the proposed `StrmUrlMapping` table and fields in the relevant spec or developer docs.
- No runtime behavior changes; no migrations or DB writes added yet.

## SQLite / Migrations Reality Check

Right now we have no DB migrations. The database is effectively ephemeral and gets deleted in `/docker/entrypoint.sh`. Adding a new table means we need a migration story, but SQLite is painful here:

- There’s no “easy” migrations tool out of the box for SQLModel + FastAPI + SQLite (no Flyway-like experience; no Drizzle/Prisma style tooling).
- An approach could be “Add Alembic migrations for database schema management with SQLModel” (like PR #14 ) but it’s been open for 2+ months and the current state doesn’t work.
- Django has `sqlmigrate`, but we’re not on Django.
- There’s a third-party tool: https://github.com/simonw/sqlite-migrate — but it’s “early alpha” with no commits in ~2 years, so it may not be safe.

Basically: if we introduce a new table for STRM refresh mapping, we also need to solve migrations (or at least decide how to handle schema changes) or this will be brittle.

## Out of Scope (for this issue)

- Implementing refresh endpoints/CLI
- Automatic refresh on playback
- Live dead-link probing or retries
- Sonarr behavior changes

---

### Comment by @Zzackllack at 2026-01-11 02:21:01.000 UTC

The current STRM implementation writes *provider/CDN-resolved URLs* into the `.strm`. That breaks in real-world setups where providers bind URLs to IP/ASN/headers/tokens: AniBridge resolves via Gluetun/VPN egress, but Jellyfin plays from a different egress and gets 403.

## Proposed direction: STRM should point to AniBridge, not the CDN (proxy-stream endpoint)

Instead of storing the resolved CDN URL in the `.strm`, store a stable AniBridge URL, e.g.

`https://<ANIBRIDGE_PUBLIC_BASE_URL>/strm/stream?site=...&slug=...&s=...&e=...&lang=...&provider=...`

Then AniBridge becomes a **byte proxy**:

- Jellyfin always requests AniBridge (reachable on LAN/WAN).
- AniBridge fetches the upstream bytes from the provider/CDN using its own network namespace (Gluetun/VPN), so IP/ASN-bound URLs work.
- IMPORTANT: this must not be a 302 redirect, because redirect would make Jellyfin hit the CDN directly again (wrong IP). We need full proxy streaming + Range support.

## “Refresh on failure” baked into the proxy

The proxy endpoint should detect dead/blocked upstream URLs (403/404/410/451/429/timeouts) and re-resolve the episode URL using the same resolver logic used during STRM generation, then retry once. This becomes “automatic refresh on playback” without requiring manual STRM regeneration.

## DB/migrations note

We can avoid a hard dependency on DB migrations by encoding episode identity in the proxy URL (stateless). Optional caching can be:

- in-memory TTL cache (no migrations),
- and later a persistent mapping table (StrmUrlMapping) once migration story is solved.

## Config knobs (high level)

- STRM_PROXY_MODE: `direct` (current), `proxy` (new), maybe `redirect` (for non-IP-bound cases).
- STRM_PUBLIC_BASE_URL: the URL Jellyfin can reach for AniBridge.
- STRM_PROXY_AUTH: optional token/HMAC to prevent open proxy abuse.

This approach solves IP/ASN binding cleanly and also provides a natural place to implement dead-link refresh logic.

<!-- Original Text: Instead of using the CDN/fetched URL in the .strm file, instead use an AniBridge proxy URL -> new env variable. Which domain does the AniBridge container have for the media player, e.g., Jellyfin. Then the request gets sent from the media player over and over again to Anibridge, which in that case works as a proxy and checks if the URLs return a valid HTTPS status code or 403/404, etc. If valid, just proxy the request through to the media player but with the IP/headers, etc., from AniBridge that resolves any issues if the CDN binds the URL to the IP/ASN/other parameters in a request and therefore the request on the media player fails to the CDN but works on the AniBridge container because the AniBridge container uses an IP like glutun. If not valid, read which URL that was (the URL has an identifier, which gets saved in the SQLite database in a new table with values such as identifier/ID, season (if not a movie), episode (if not a movie), and provider), then just refetch to a new CDN URL using the same procedure as used when an episode/series is requested via Sonarr. !-->

---

### Comment by @Zzackllack at 2026-01-11 02:30:48.000 UTC

Most STRM entries we generate point to HLS `.m3u8` URLs (master playlists). That changes the proxy story significantly:

**HLS is not a single request.** ffmpeg/Jellyfin will fetch:

1) master `.m3u8`
2) one or more variant/media playlists referenced by the master
3) many segment URLs (`.ts` / `.m4s` / `.mp4`), plus potentially `EXT-X-MAP` init segments and `EXT-X-KEY` key URIs, and sometimes audio/subtitle playlists.

So a “simple byte proxy for the master.m3u8” is not enough. If we return the original segment URIs unchanged, ffmpeg will request segments directly from the CDN again (different IP/ASN) and we’ll still hit 403.

## Proposal: HLS-aware proxy (playlist rewrite + segment/key proxy)

When AniBridge proxies a `.m3u8`, it should:

- fetch the upstream playlist via the VPN egress,
- rewrite *all* URIs inside the playlist to AniBridge proxy URLs (variant playlists, segments, EXT-X-KEY URI, EXT-X-MAP URI, EXT-X-MEDIA URI, etc.),
- serve the rewritten playlist to Jellyfin/ffmpeg,
- and implement a generic proxy endpoint that streams bytes for the rewritten URIs (segments/keys/init).

This is the standard “HLS playlist rewrite proxy” pattern.

## Refresh-on-failure fits naturally here

If upstream returns 403/404/etc for a playlist/segment, the proxy can re-resolve the provider URL (same logic as STRM generation) and retry once, then update cache/mapping.

## Implementation notes

- Use an HLS parser (e.g. Python `m3u8`) or robust line-based rewriting to also handle URI attributes (`EXT-X-KEY`, `EXT-X-MAP`, `EXT-X-I-FRAME-STREAM-INF`, `EXT-X-MEDIA`, `EXT-X-SESSION-KEY`).
- Don’t redirect (302) to CDN. Must proxy bytes; redirect would make Jellyfin hit CDN directly again.
- Add auth/signing to avoid becoming an open proxy.

This should solve the CDN IP/ASN binding issue for HLS-based STRM playback.

---
