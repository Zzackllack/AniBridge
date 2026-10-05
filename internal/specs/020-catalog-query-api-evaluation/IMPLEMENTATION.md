# Request catalog private pilot

Selected 2026-10-05 for the maintainer's explicitly configured private pilot.
Base: current main `e14a041c0a8ddeac71aab7b8f564ac4a9584603a`, released
v2.6.0. Reference heads remain untouched: worker `88b8796`, evaluation
`4786f6e`. Historical evaluation/019 documents retain their original status.
This document supersedes **client snapshot distribution only**. It does not
approve public hosting, an outbound default, redistribution, or live collection.

## Selected contract

A collector builds an allowlisted read catalog from its durable metadata ledger.
One read-serving command in that same uv project answers authenticated POST
`/catalog/v1/query`. It never imports AniBridge startup globals, crawls on query,
extracts video or returns media URLs. Local AniBridge alone applies policy,
formats RSS, admits jobs and resolves grabbed provider/video-host content.

Operations are title/ID candidate discovery, native-title batches, and recent
release pages. Title discovery returns stable title IDs, aliases and canonical
ID associations; IDs and normalized prefix title text intersect. Ambiguous IDs
remain unresolved. Native batches select stable title IDs and return observed
entity/language variants and conservative canonical maps without canonical
season filtering. Ordinary seasons fit one batch; larger titles use bounded
pages, never per-episode network requests. A local correction's stable title ID
is included in candidate discovery. Corrections stay on the local installation.
Complete candidate batches are corrected before ID/season/episode/language,
category and mode filtering, exact totals and final pagination. Excessively
broad/large candidate sets fail explicitly instead of returning truncated totals.

Retain 019 provider-scoped SHA-256 title/entity/release IDs, source paths and
native coordinates, canonical namespace/ID and explicit episode coordinates,
positive language observations, first_seen_at across rebuild/reappearance, and
v2 self-contained magnets. No inferred numbering, quality, codec or size. TMDB-only episode requests use
explicit TMDB coordinates; TVDB remains the default for TVDB/title searches.
First-seen means discovery, including historical bootstrap. GUIDs/infohashes do
not change with mapping/title/quality corrections. No local search-time media
sampling or canonical/provider network fallback is enabled in this pilot.

Finite limits: eight simultaneous server/local queries; 2-second cooperative
SQL budget and 3-second HTTP deadline; 15-second total local search deadline;
16-KiB request, 2-MiB response, 200 candidate titles, 500 native releases/page,
2,000 native releases/search, 100 RSS results/page and offset <=10,000. Global
server token bucket 200/s, burst 256; no per-IP table. Ninth active operation is
rejected. Disconnect/timeout signals SQL cancellation; slots remain held until
threads settle. Kernel-stalled I/O is not a hard real-time guarantee. Multi-page
reads must agree on revision; one restart is allowed, then fail explicitly.
Recent pages have exact filtered totals and deterministic first_seen/release
ordering. Cross-request offset pages may straddle updates: overlap polling and
GUID deduplication are required; stable GUIDs alone do not prove lossless polling.

Server read catalogs are immutable, allowlisted SQLite files. A process-shared
read/write file lock pins each response and fences replacement/cleanup. Build
one staging file, validate it, atomically replace current under exclusive lock.
No compression/signature distribution pipeline or historical catalog archive is
needed. Keep durable worker state, one current read file, bounded staging,
existing migration backups and logs within 30,000,000,000 bytes including a
1,000,000,000-byte runtime reserve. Reject builds/admission under disk pressure.
Collector and query serving have independent finite work limits.

Local cache: source/origin/token fingerprint/protocol/complete request keys,
128 entries, 2 MiB serialized payload and 16 MiB SQLite page cap. TTL 60 seconds;
positive validated stale responses allowed for at most 24 hours after fetching,
only on transport/timeouts/503/429. Authentication/contract/replay failures are
explicit failures. Negative responses never hide outages. Stored bytes are
revalidated on every hit. Source changes cannot reuse prior data. Persist a
per-source/provider revision floor; older entries must refresh, and older network
responses fail. Same-key misses share one bounded task; one cancelled waiter
does not cancel other waiters. Distinct misses are capped at eight. No background
cache coverage guarantee. A cold outage returns HTTP 503/XML error 900. Stale
RSS is identified by X-AniBridge-Catalog-Stale and age headers; clients may ignore
headers, so this is diagnostic metadata rather than a UI promise.

Trust: explicitly selected HTTPS origin, normal certificate verification,
source ID and bearer credential from a local file. No redirects or environment
proxy inheritance. Loopback HTTP is allowed; the disposable Docker network can
use HTTP only with an explicit private-network opt-in. Response allowlists,
size/identity/path/language/query/revision validation replace client whole-file
Ed25519 admission. This trusts the configured operator for metadata correctness;
identity validation is not authenticity proof. Do not send credentials on error
or access logs. No raw query/IP logging by default. Search terms/IDs and client
IPs are disclosed to the configured service; reverse proxies/TLS terminators and
operators can observe requests even with application access logging disabled.

## Compatibility and restoration

Absent CATALOG_CONFIG_FILE preserves mainline search routes. This compatible
build still performs additive private-schema migrations with a preupgrade
backup; it does not promise an unchanged v2.6.0 database. An explicit
query-mode file enables only this pilot, initially AniWorld. No permanent backend
framework or snapshot consumer mode is added. Additive private schema changes
retain released mainline data, Job/ClientTask hashes, STRM mappings and files.
Reuse exact mainline preflight/backup and conservative legacy-job recovery from
019, including refusal of foreign schemas. Accepted jobs freeze source identity,
path/native coordinates/language/canonical label and run independently of API
availability or catalog replacement. Pause/block/retry/generation-CAS/restart
behavior stays local. Existing jobs remain viewable; incomplete legacy requests
are preserved with explicit failure reasons. Default STRM paths remain intact.

Restoration: stop writers, remove pilot opt-in, use this compatible build with
legacy routes. Preserve all durable requests; do not let legacy startup mark them
failed. Downgrading to v2.6.0 requires the retained preupgrade backup and matching
files; post-backup jobs would be lost, so prefer forward restoration. The
maintainer pilot uses disposable volumes and never migrates a real installation.

## Reuse map

| Component | Existing location on worker/evaluation refs | Action | Reason |
| --- | --- | --- | --- |
| Provider parsers/transport | catalog-core/providers | retain | Observed languages, safe bounded metadata access; other adapters available |
| Incremental ledger/scheduler | catalog-worker/state, collector, pipeline, signals | retain | Durable first-seen/checkpoints and one writer |
| Canonical matching | catalog-worker/canonical, mapping, review | retain | Conservative evidence and explicit season correspondence |
| Indexed query/parser | API catalog/search | extract/adapt into catalog-core | No API globals in serving project; local overlays remain local |
| Identity/magnets/schema | catalog-core | retain | Frozen source identity, stable GUID and grab contract |
| Strict wire/cache | scripts/catalog/query_api | adapt | Add coalescing, revision floor, native batches and production path |
| Corrections | API catalog/overrides, override_view | retain/adapt | Pre-filter precedence and fingerprint/conflict checks |
| Durable jobs/executor/STRM | API catalog/jobs, runner, executor, client, local children | retain | Avoid rewriting working lifecycle/media components |
| Mainline migration protection | API db/preflight, legacy_catalog and additive migrations | retain | Preserve private data and foreign-schema refusal |
| Export | catalog-worker/export | retain | Allowlisted server-only catalog, compact indexes |
| Snapshot client/update/admission/receipts | API catalog/store, update, activation, refresh_child | omit | No full client catalog transfer/validation |
| Signed/compressed publication and full retention harness | worker publisher, static server; scripts/catalog | omit | No consumer artifact distribution or 24-hour repetition |
| Focused tests | core/worker/API/evaluation tests | select | Keep contract/failure proofs without importing full gate matrix |

## Decisions and evidence boundary

The user authorized this explicit private/self-hosted transition and request
privacy tradeoff. Finite cache/time/resource defaults above are engineering
choices. No maintainer decision blocks local implementation. Remaining product
choices: any public source/default, redistribution rights, supported-client
quality profiles, broader providers/platforms and SLA/capacity/cost promises.

Keep a concise EVIDENCE.md checklist. C0 identities/mapping, C1 collection,
C3 migration, C5 client/lifecycle, C6 bounded storage remain applicable in narrowed
form. Replace client artifact admission/renewal/transfer gates with authenticated
response validation, revision/cache/outage/coalescing and consistent-reader tests.
C7/C8 public/platform gates remain closed. Both old endurance validation timeouts
remain failed historical evidence, including the unexplained second timeout.
This pilot neither explains nor fixes them. Deterministic fixtures, actual *arr
fixture clients, live provider extraction, import and playback are separate proofs.
