# AniBridge consumer, search and upgrade

[02](02-architecture-and-contract.md) owns update/security/retention;
[09](09-artifact-schema-and-identities.md) owns identity/schema;
[08](08-decision-follow-up.md) owns jobs, sampling, fallback and management.
No catalog-worker request contains a user's search text, ID or demanded title.
Provider requests and video extraction for playback/grabs run on the user's
AniBridge instance with its configured origins and network policy.

## Configuration and transition

One new environment variable `CATALOG_CONFIG_FILE` points to a local JSON file;
missing means legacy mode before the hosted-launch build. File fields:
`mode` (legacy or snapshot), `source` ({source_id, url, keys: array of raw
base64 Ed25519 public keys, allow_lan_http: boolean}), `local_refresh`
(off or explicit_targeted, default off), `canonical_sources` (08), and `limits`.
All unknown keys, duplicate keys, invalid URLs/keys or out-of-range values fail
startup, never silently revert to an insecure source. `source` required in
snapshot mode until official defaults are released. Continue using existing
`CATALOG_SITES`; no second enabled-provider setting. Management token is the
separate `MANAGEMENT_API_TOKEN` env setting (08). Update env example/docs only
when implementing these variables, not during this specification task.

Consumer `limits` fields (defaults, allowed inclusive range):

| Key | Default | Range |
| --- | ---: | --- |
| poll_interval_s | 1800 | 300–86400 |
| compressed_bytes | 268435456 | 1 MiB–512 MiB |
| sqlite_bytes | 1073741824 | 16 MiB–2 GiB |
| catalog_disk_bytes | 8589934592 | 2–64 GiB |
| sample_queue | 32 | 1–128 |
| sample_deadline_s | 20 | 5–30 |
| sample_bytes | 16777216 | 1–32 MiB |
| sample_ttl_s | 86400 | 3600–604800 |
| job_queue | 1000 | 1–10000 |
| refresh_queue | 32 | 1–128 |
| private_metadata_bytes | 17179869184 | 1–100 GiB |

All other limits in 02/08 are fixed v1 constants to avoid unnecessary knobs.
Size relationships must permit at least one candidate and reserve; invalid
config fails startup. Lowering disk quota below protected existing bytes keeps
search/jobs usable and blocks new updates/admissions, never deletes state.
Poll with a stable provider offset within the interval; do not add random delay
beyond the freshness budget. On startup use saved catalog immediately and
schedule background poll. Conditional GET saves bandwidth; no polling in search. Identical signed
renewals use02's source/pin-bound digest receipt without an artifact-body
transfer. New private migration0008 adds nullable trust context to existing
receipts; older pilot rows are preserved and receive one full bounded semantic
recheck before fast recovery/renewal. Released-mainline data remains intact.
The existing120s validation and900s total update budgets stay unchanged.

Before public gates pass, existing installs remain on legacy search unless
explicitly configured for the private/self-hosted snapshot pilot. Once the
hosted-default launch build passes C7/C8, new installations use snapshot mode
with bundled official source/key configuration. On upgrade, an absent explicit
config stages official snapshots in the background, keeping legacy **per
provider** until that provider has validated release data; then persist its
one-way transition to snapshots. Explicit source/legacy selections win and
are never overwritten. After transition an outage keeps last-good snapshots;
it never silently resumes live search probes. This temporary legacy bridge is
upgrade compatibility, not a second selectable hosted-search backend.
Document new source traffic in release notes before this build ships.

For snapshot mode, caps is independent of catalog/network availability. Keep
API liveness HTTP 200 when DB/scheduler work, add catalog readiness separately;
new `GET /ready` is 200 if every enabled provider has an active validated
artifact, 503 otherwise. Detailed status requires management auth. GET /ready body is only `{"ready":true}` or
`{"ready":false}`, with no provider/detail disclosure. At least
one provider ready means partial readiness; it is useful, not full readiness.
The ready/partial provider states both count as usable for /ready and searches.
An empty but validated release set remains usable with incomplete coverage;
a title-only first artifact is not sufficient for automatic legacy transition.

## Search API and failure behavior

`/torznab/api` preserves current query names, API-key behavior and XML namespace.
Caps advertises implemented modes/IDs, limits default 100/max 100, no season
packs. `t=movie-search` aliases `movie`. Snapshot searches use parameterized
indexed SQL, one captured provider-handle set per response, SQLite cache
8 MiB/connection, mmap disabled, maximum 8 simultaneous search requests and
24 catalog connections. SQLite private-DB reads for overlays use a pinned read
transaction acquired with the catalog handles; override writes increment its
version. Do not block activation while waiting for canonical HTTP: perform ID
fallback before acquiring the final search snapshot. Ninth request gets HTTP 503/Retry-After 1. Each query
has 2s wall budget (progress handler), including bounded count/pagination;
ID fallback adds at most 2s. Deadline exceeded is an error, never truncated
success disguised as complete results.

| Condition | Response |
| --- | --- |
| caps | HTTP 200 XML even when catalog is unavailable |
| all selected providers unavailable | HTTP 503, Retry-After 60, XML `<error code="900" description="Catalog temporarily unavailable"/>` |
| some selected providers ready | HTTP 200 RSS over ready providers; `X-AniBridge-Catalog-Partial: true`, missing provider keys in `X-AniBridge-Catalog-Unavailable` |
| complete search, zero matches / unresolved mapping | HTTP 200 empty RSS, total=0; `X-AniBridge-Mapping: unresolved` when applicable |
| malformed query/ID/coordinates/limit | HTTP 400 XML error code 200 |
| unsupported function/ID namespace | HTTP 400 XML error code 202 |
| configured indexer key wrong/missing | existing authentication error, never successful RSS |
| query deadline / required canonical source timeout | HTTP 503 XML error code 900; Retry-After 60 |

900 is an AniBridge extension for transient service failure, not a claim that
Torznab standardizes it; the HTTP status is authoritative. C5 tests Prowlarr's
handling before release. Partial feed totals describe available providers only.
Clients may ignore diagnostic headers; management status is authoritative.
No phantom connectivity item. Disable the legacy test-result behavior on the
snapshot path; keep it only while an upgrade provider still uses legacy mode.

Explicit title query finds exact/prefix candidates via 09. `tvsearch` requires
known canonical mapping for requested season/episode; `season` is an integer
>=0, `ep` is absent or a positive integer. For released-client compatibility,
`ep=0` means whole season as it does on mainline; negative/noninteger ep errors.
Never assume provider
ordinals. With q only, return known mapped episodes for matched series, all
seasons subject to pagination. ID and q supplied together must agree; conflicting
IDs return empty/unresolved, not title-based fallback. Local corrections precede
published mappings; unresolved is last. Specials use explicit season 0 maps.
`t=search&q` may expose provider-native labels for unmapped episodes, marked
`X-AniBridge-Mapping: partial`; they never answer a canonical episode request.
`t=movie` selects actual movie entities, optional year/IDs; no fake S01E01.
No release exists without a positively observed language in the active catalog
or a valid targeted local overlay. Filter language using existing configuration
intersected with observed variants. Do not use configured default languages as
availability. No provider/video-host/media-manifest probe blocks any search; the only
network exception is the bounded canonical-ID fallback in 08.

## Recent RSS and pagination

No q/IDs/season/ep means recent feed for search, tvsearch or movie. TV/movie
modes filter entity kind; `cat` accepts comma-separated numeric categories,
intersected with configured anime/TV/movie category mapping. Unsupported valid
categories yield zero results. Default recent window 30 days by first_seen_at;
`maxage` integer 1–30 narrows it. Explicit searches have no recent-window filter.
Season/ep without q or ID is malformed. Numeric limit 1–100, default 100;
offset 0–10000; larger/negative values error, no silent clamping. Large backlogs
must be narrowed by query/category/maxage; do not promise unbounded enumeration.

Apply provider/kind/category/language/window filters before total and pagination.
Count emitted mode variants (`STRM_FILES_MODE` no/both/only), sort
`first_seen_at DESC, release_id ASC, mode ASC`. `newznab:response` reports exact
filtered total and requested offset; offset past end returns empty with that
total. pubDate is first_seen in RFC 1123 GMT. GUID/infohash from 09 are stable
across estimate/title/mapping corrections. No season packs. Bootstrap therefore
shows newly discovered historical entries within this window; it does not
claim they aired recently or command clients to download unmonitored content.

Supported clients distinguish historical discovery from RSS. A fresh indexer
may stop after its first RSS page when it has no saved cursor. Existing monitored
missing episodes/movies must be discoverable through the client's normal manual
search or explicit automatic search/missing-item workflow; initializing a catalog
must not download unmonitored content. AniBridge neither stores *arr credentials
nor commands library-wide searches or supplies a backfill service.

Normal RSS handles new releases and catch-up using the client's persisted cursor.
C5a measures tied-second bursts, interrupted polling within a controlled 23-hour
cursor gap and restart, with normal client backoff. This is not a 23-hour wall-time
freshness/endurance result. Beyond the client/retention window, follow the client's
missing-item search workflow; a stable GUID cannot repair an uncovered cursor gap.

Each response pins catalogs and overlay version while querying. Offset requests
across activations are not a multi-request transaction: duplicates/skips can
occur. Poll from offset zero with overlapping windows; stable GUIDs deduplicate.
C5 must test whether supported *arr polling can drain the measured worst-case
new-release volume without permanent loss. If it cannot, gate release and
revisit pagination/window throughput; do not claim GUIDs alone prevent skips.
Reappearance retains old date (outside window remains outside); language added
later has a distinct new date. Source switch keeps stable IDs where anchors
agree; it cannot preserve another publisher's unknown discovery history.

Release names omit height/codec tokens when unknown; do not use SD, H264,
720p or a synthetic source-quality token as fallback. Exact episode observations
may label measured quality; inherited scoped height is labelled `Estimated`
and remains a client-parsed quality estimate, not proof. Do not inherit codec
or size. Unknown byte size uses RSS enclosure length=0 and Torznab size=0;
no mainline heuristic. This representation and unknown-quality profiles are
C5 hypotheses to validate, not guaranteed *arr acceptance. Identity never
changes with size/label. Actual completed files use measured naming where
available. Source hints stay outside v1 artifacts.

## Local overlays

Override precedence: enabled nonconflicting local correction > validated
published map > unresolved. Key by provider/entity ID and mapping namespace;
retain reason, target, version, provenance and input entity fingerprint.
Conflicting/disappeared target suspends application, preserves the override and
reports conflict; never silently points to another entity. Deletion restores
published behavior. An override can intentionally resolve a missing map, with
validated canonical ID/coordinates and explicit local operator provenance.

Targeted refresh (only explicit_targeted) accepts existing title IDs, never URLs.
One title task, bounded by worker-style slice/rate/path rules with 120s total
wall deadline and 30 requests; incomplete work reports partial, not absence.
Separate private observations override older observations for the same stable
entity only after successful validation. Expire after 24h or supersede when
central observed_at >= local observed_at. Failures never hide central data;
new local releases preserve their private discovery ledger, and central arrival
uses min(local,central first_seen) locally for that ID. Overrides do not expire.

## Supported upgrades and rollback

Support released-mainline Alembic revisions 0001→0003 and the exact pre-Alembic
schema recognized by current migration tests. Backup using SQLite backup API,
fsync backup, inventory tables/row counts/download paths before migration;
verify known schema before modifying anything. Additive migrations preserve
jobs, ClientTasks, availability, STRM mappings, settings and files. Reject
unknown/PR #119 schemas without stamp/drop or compatibility layer.

Legacy Job lacks a complete request payload; reconstruct only from a unique
linked ClientTask with proven fields. Preserve existing hash and source_site.
Mode/provider hint missing from persisted state must not be guessed (e.g.
STRM from a display name). Keep ambiguous interrupted jobs as failed with
`legacy_request_incomplete` and operator-readable reason; do not delete or
resume them as a different request. Already completed paths remain unchanged;
queued legacy records with complete provable request can enter the new queue.
Replace mainline cleanup_dangling_jobs for new durable jobs (08).

Keep a preupgrade backup until operator removes it; it is private operational
storage outside disposable catalog quota. Image downgrade requires stopping
writers and either a tested additive-schema-compatible downgrade or restoring
the backup plus its matching catalog state. Backup restore loses post-backup
changes, so it is not the routine rollback: prefer forward repair. Never run
an old image blindly against a newer private schema. Release notes include
migration rehearsal evidence and exact supported downgrade range. No major
version permission to delete user data.
