---
title: Catalog Query Mode (Advanced)
outline: deep
---

# Catalog Query Mode (Advanced)

::: warning Advanced, operator-configured setup
Catalog query mode is not the normal public setup. It requires a metadata collector
that you run or otherwise control, plus a collector origin, source ID, and bearer
token. There is no approved hosted, token-free catalog endpoint yet. A zero-config
official public metadata catalog is planned, but it is not shipped.
:::

AniBridge has two search paths:

| | Legacy (default) | Query mode |
| --- | --- | --- |
| Search source | Live provider scraping per request | Previously published collector metadata |
| Providers | AniWorld, s.to, megakino | AniWorld, s.to, megakino, optional Filmo movies |
| Numbering | Provider season/episode used directly | Canonical `SxxEyy` when published, native numbering otherwise |
| Media download | Local yt-dlp download | Local yt-dlp download, same as legacy |
| Status | Deprecated, still functional | Advanced/private preview; opt-in |

Query mode changes where search results come from. It does **not** move media
downloads to the collector or to a hosted service. Imports, completed files, TTL
cleanup, and STRM handling remain local.

## Requirements

Set all of the following in the API environment:

- `CATALOG_MODE=query`
- `CATALOG_API_URL`: HTTPS origin root, for example `https://catalog.example.invalid`.
  It must not include a path, query, fragment, or embedded credentials.
- `CATALOG_SOURCE_ID`: 1–64 characters from `a-z`, `0-9`, `.`, `_`, and `-`.
- Exactly one of `CATALOG_API_TOKEN` or `CATALOG_API_TOKEN_FILE`. Tokens are
  16–512 visible ASCII characters with no spaces. A token file path is resolved
  inside the API container and should be a read-only mounted secret.
- `CATALOG_SITES` must list the providers your collector publishes (default
  `aniworld.to,s.to,megakino`; add `filmo.to` for movies).
- `DB_MIGRATE_ON_STARTUP=true`. Query mode refuses to start when migrations are
  disabled.
- Linux for the local job sandbox. On macOS or Windows, run the API in Docker.

Query mode also requires writable state on a filesystem that enforces process
locks. Docker Desktop bind mounts on macOS can accept conflicting `flock` owners;
use a Docker named volume or Linux-local storage for `DATA_DIR`. Deleting a lock
file does not fix the filesystem.

Plain HTTP is accepted only for loopback origins unless you set
`CATALOG_ALLOW_PRIVATE_HTTP=true`. That opt-in permits unencrypted HTTP to any
non-loopback host; it does **not** restrict traffic to private addresses. Use it
only on a trusted test network.

```ini
CATALOG_MODE=query
CATALOG_API_URL=https://catalog.example.invalid
CATALOG_SOURCE_ID=my-source
CATALOG_API_TOKEN_FILE=/run/secrets/catalog-token
CATALOG_SITES=aniworld.to,s.to,megakino
DB_MIGRATE_ON_STARTUP=true
```

The API reads catalog query settings from environment variables only. The old
JSON setting `CATALOG_CONFIG_FILE` is removed: any non-empty value fails startup
instead of silently falling back to legacy. The collector's own JSON config
(for example `apps/catalog-worker/config.example.json`) is separate and is not
read by the API.

## Enabling and upgrading

1. Stop the API and take a backup of `DATA_DIR` (including SQLite WAL data).
2. Collect metadata with your collector so the configured source has a published
   catalog. AniBridge does not crawl providers at API startup.
3. Set the environment values above and start the API.
4. Verify `GET /torznab/api?t=caps`, then run a text search before wiring IDs.

Returning to legacy mode means clearing `CATALOG_MODE` (or setting it to
`legacy`). Legacy mode is deprecated and may be removed later, but it remains the
default in stable builds. Query mode and legacy mode use the same SQLite
database. Query mode applies additive migrations and retains a pre-upgrade
backup named `anibridge_jobs.db.pre-catalog-v3.backup`; older builds may not
accept an already upgraded database. Test rollback using a separate restored
copy, and preserve jobs created since the backup rather than overwriting newer
state. A custom database filename changes the backup filename as well.

Filmo is rejected in legacy mode at startup. Enabling `filmo.to` requires query
mode even if you only want to configure the provider.

## Query bounds and limits

Query mode is deliberately bounded:

- `limit` is 1–100 (default 100); `offset` is 0–10000.
- Title discovery matches at most 200 candidate titles. A broader text match is
  rejected as `query_too_broad` instead of being truncated.
- Native episode/movie expansion is capped at 2,000 releases per title set.
  Larger matches are rejected, not silently paged.
- Recent pages (`t=search` with no text, ID, season, or episode) return at most
  100 rows. `maxage` is 1–30 days (default 30).
- The overall provider search deadline is 15 seconds; local SQLite work has a
  2-second deadline per provider; each metadata request has a 3-second deadline.
- At most 8 searches run concurrently, with 8 metadata connections. Query jobs
  run at most 2 concurrent downloads (or `MAX_CONCURRENCY` if lower), each with a
  256 MiB child allowance.

`rid` and `tvmazeid` are not supported in query mode. `movie-search` is treated
as `movie`.

### Partial results and errors

If one provider is unavailable, reachable providers still return rows. The
response then carries:

- `X-AniBridge-Catalog-Partial: true`
- `X-AniBridge-Catalog-Unavailable: <provider>,...`

If no provider succeeds, or any provider fails and the remaining results are
empty, AniBridge returns HTTP 503 with Torznab error code 900 and `Retry-After`
instead of an empty success. A busy search uses a shorter retry delay. `t=caps`
still works during a metadata outage.

Invalid requests and bounded-query violations return HTTP 400. `query_too_broad`
is a caller error, not an outage.

## Cache, stale data, and outages

The local metadata cache is a disposable SQLite file under `DATA_DIR/catalog`:

- At most 128 pages and 2 MiB of payload.
- Pages are fresh for 60 seconds.
- On transport failure, timeout, HTTP 429, or HTTP 503, a previously cached
  **positive** page may be served stale for up to 24 hours. Stale responses are
  marked `X-AniBridge-Catalog-Stale: true` with
  `X-AniBridge-Catalog-Age: <seconds>`.
- Empty cached pages are never used to hide an outage.
- A revision regression or a snapshot change during a multi-page query clears
  that provider's cached pages and retries once. Persistent drift returns 503.

Cache and revision state are scoped to the origin, source ID, and a fingerprint of
the bearer token. Switching source or token does not reuse the previous source's
pages. If cache initialization fails, search stays unavailable while accepted
local jobs continue. Invalid cached responses are ignored; a payload write
failure can still return a validated live response. Unavailable revision state
fails search explicitly to prevent revision rollback.

There is no offline catalog. A cold outage, an invalid token, or a source that
has never published metadata returns an explicit 503.

## Numbering and ID matching

Query results use canonical `SxxEyy` numbering when the service publishes an
episode mapping. Otherwise AniBridge emits the provider's native season/episode
and does not guess a mapping. Movie rows append the observed year for Radarr.

ID-based searches (`tvdbid`, `tmdbid`, `imdbid`) only match titles with published
canonical mappings. When an ID search returns nothing, the response includes
`X-AniBridge-Mapping: unresolved`. Selected rows without canonical coordinates
produce `X-AniBridge-Mapping: partial`. Text searches can still return unmapped
titles with native numbering.

AniBridge does not translate Sonarr's "Anime/Absolute" episode requests into
provider seasons/episodes, and it does not rewrite output numbers to absolute
form. Sonarr must send coordinates that match the provider or a published
mapping.

## Filmo movies (optional)

Filmo adds movie offers to query mode. It is off unless all of these are true:

- `CATALOG_MODE=query`
- `CATALOG_SITES` includes `filmo.to`
- The collector publishes `filmo.to` metadata
- `FILMO_BASE_URL` matches the verified Filmo origin used for local grabs
  (default `https://filmo.to`)

Legacy mode with Filmo configured fails startup.

Filmo releases preserve each native offer as an explicit source variant. Titles and
metadata distinguish:

- Declared audio languages, including multi-audio offers. A multi-audio release
  is one selectable item and matches any requested declared track language.
- Subtitles separately: soft, hard, none, or unknown. Subtitle claims are never
  reused as audio claims.
- Declared quality labels. A quality token is emitted in the release title only
  when Radarr can represent it without guessing. Generic `WEB` or resolution-only
  claims remain in attributes and the description.
- Unknown audio (`und`) is not advertised as a known spoken language. Offers
  without a known audio track are not selectable through the Torznab language
  set.

Only offers on supported hosts (VOE and Byse) are selectable. Offers on other
hosts are filtered out before counts and pagination. Selecting a Filmo release
re-resolves and verifies that exact offer locally before download; it does not
download media through the metadata service.

For Radarr, add the AniBridge Torznab endpoint as a movie indexer and the
AniBridge qBittorrent shim as the download client. Movie releases use category
`2000`. A movie without a published `tmdb-movie` or `imdb` mapping can still be
found by text, but ID searches will report unresolved mapping and may be unusable
for automatic Radarr matching.

## Local jobs, progress, and completion

Query jobs are durable and local:

- `progress` is reported from 0 to 1. A completed transfer stays at 100% only
  after the final file is published.
- Progress lines are written per job, so concurrent jobs do not share a bar.
  `PROGRESS_FORCE_BAR` and `PROGRESS_STEP_PERCENT` retain their usual meaning;
  query downloads also keep stepped progress lines in saved logs.
- If Sonarr or Radarr moves or deletes an imported source after completion, the
  job remains completed: `progress` stays 1, state is `pausedUP`, and no
  `content_path` or file list is exposed for the missing path. The client sees
  `anibridge_output_missing: true`. AniBridge does not rewrite the transfer to
  `failed`, `error`, or `missingFiles`.
- `DOWNLOADS_TTL_HOURS` cleanup can remove old media from `DOWNLOAD_DIR`. It
  removes known video extensions only and skips directories owned by active jobs.
  It does not delete `.strm` files. Expired files use the same completed-and-
  missing representation described above.
- `DELETE_FILES_ON_TORRENT_DELETE=true` removes the AniBridge-owned source file
  when the client deletes the torrent, after the final alias is removed.

Optional local management endpoints are available at `/api/v1/jobs/{id}`,
`/retry`, and `/cancel` when `MANAGEMENT_API_TOKEN` is set. The token must be
base64url encoding of at least 32 random bytes. Without it, management endpoints
return 503. Retry is only offered for failed or blocked jobs.

## Security boundaries

Query mode adds another credential and another network path; it does not weaken
the existing local API boundaries:

- `CATALOG_API_TOKEN` is used only for outbound metadata requests. It is never
  returned by the local API.
- `INDEXER_API_KEY` protects only `/torznab/api`.
- `QBIT_USERNAME` / `QBIT_PASSWORD` / `QBIT_SESSION_SECRET` protect only
  `/api/v2`. Leaving them empty keeps unauthenticated compatibility on a trusted
  private network.
- `STRM_PROXY_AUTH` / `STRM_PROXY_SECRET` protect `/strm/*` and are independent
  of the indexer and qBittorrent auth.
- `MANAGEMENT_API_TOKEN` protects the local job management endpoints and is
  independent of the collector token.
- In query mode, Uvicorn access logs are disabled so local query terms and IDs
  are not written to the API access log. The collector operator can still observe
  search terms, IDs, and your service-visible IP. AniBridge makes no proxy or
  third-party log-privacy guarantee.

The local API still needs its own protection: bind it to a trusted network, put
TLS in front of it when clients are remote, and do not expose an unauthenticated
qBittorrent or STRM endpoint to the Internet. CORS settings apply to the whole
application and do not replace authentication.

## Preview builds and stable builds

Stable release images (`:latest` and version tags) are cut from the default branch
and keep legacy search as the default. The catalog query work is developed on the
`v3` integration branch and published through separate preview image packages.
Preview images are not stable releases, are not the `:latest` release image, and
must be pinned by digest for repeatable deployments. Check the selected image's
labels and source commit before assuming query mode is present.

Do not assume a blind pull/restart is a safe preview upgrade. Collector ingress,
bind addresses, mounts, and tokens are deployment-specific; review and test the
collector configuration alongside the API image before upgrading an existing
deployment.

## Current limitations

- No hosted, zero-config public metadata catalog exists yet. The planned official
  catalog will remove the need for users to enter a metadata URL or token.
- Query mode depends on collector freshness and mapping quality.
- Filmo automatic ID matching needs published movie mappings; text/year matching
  can work without them but is less reliable.
- Broad or deeply paged queries are rejected by design.
- Legacy search remains deprecated; new work targets query mode.

See [Environment](/api/environment) for every variable and
[Torznab API](/api/torznab) for request/response behavior.
