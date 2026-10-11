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
pages, never per-episode network requests. Canonical coordinate selectors narrow
native batches to a superset plus local correction entity IDs. Those stable IDs
are disclosed for retrieval; reasons/fingerprints/override bodies stay local.
AniWorld default v1 wire requests remain compatible; expanded providers and
coordinate selectors require the updated service/client. A local correction's stable title ID
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
2,000 native releases/provider/search, 100 RSS results/page and offset <=10,000. Global
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

## Resource profiles and freshness (clarified 2026-10-08)

The collector/catalog index worker has a **minimum allocation of 2 vCPU and
2 GiB RAM**, including its supervised parser/publication children. The selected
recommended profile is **4 vCPU / 4 GiB RAM**. Use 6 GiB only if profiling shows
useful cache retention, publication headroom or memory pressure at 4 GiB; it is
an optional larger profile, not a requirement or a measured speed promise.
This is an operator sizing policy, not proof of complete-bootstrap capacity.
The metadata read service has a separate budget and must remain available during
collection. Host sizing must leave room for that service, the OS and other apps.

The local AniBridge target is **1 vCPU / 512 MiB for startup, idle operation,
metadata requests and search**. Extraction/job peaks and job concurrency need
separate validation; existing whole-client acceptance used 2 vCPU / 1 GiB and
does not establish that all jobs fit the smaller target. The currently deployed
2-vCPU/512-MiB worker is a deliberately constrained private test profile, not
the production minimum. Historical measurements keep their original limits.
No resource allocation or request budget changes follow automatically from this
documentation correction. The 30,000,000,000-byte storage budget remains intact.

A full bootstrap is retained across restarts; daily maintenance must not restart
it or recrawl every episode. Current collection polls recent TV feeds every
15 minutes, refreshes the title inventory every four hours, and admits bounded
targeted work, bootstrap progress and weekly historical reconciliation. Capped
recent feeds are hints, not lossless change streams; latched gaps remain visible.
The incremental path admits active title/season parents after four-hour eligibility,
and parents older than a latched feed gap, through the existing 20% hourly
reconciliation budget. Failed work still respects its retry deadline; episodes
retain weekly fallback. Status exposes pending gap parents. This is bounded
eligibility, not proof of lossless feeds or a four-hour whole-provider SLA.

Search remains catalog-only. No background demand-refresh system or synchronous
query scraping is introduced by this repair.

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
query-mode file enables only this pilot, AniWorld/Serienstream and optional Megakino. No permanent backend
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

## Implemented provider extension (2026-10-05)

Normal scheduler and read serving support independently configured AniWorld,
Serienstream (`s.to` stable identity) and optional Megakino. Each provider owns
its last-good read pointer/revision under the shared aggregate storage budget.
HTTPS origins never change public IDs. Megakino sitemap origin aliases are
explicit path-only metadata allowlists; serial titles remain unsupported, and
unlabelled player languages produce no releases. No default-German inference.

TV season correspondence can be proved by three distinct unique episode-name
anchors in one canonical season, with no conflicting uniquely matched name or
second native season claiming that season. Reviewed correspondence remains
available. Duplicate source/canonical titles and ambiguous cases stay unresolved.
Only demonstrated trailing AniWorld `[Final Episode]` and `[Episode NNN]`
annotations are fallback evidence, after exact matching; other annotations stay
unresolved. Unique individual names can prove an episode across a native season
spanning canonical seasons without proving whole-season correspondence. Source
titles and coordinates remain unchanged. An empty explicit IMDb search permits
one title-search fallback retaining that exact IMDb ID, reverified in the
descriptor; title similarity alone cannot select a canonical series.

Operator commands and coverage limits: `scripts/catalog/query_pilot/SERVER.md`.
No full provider crawl has completed on the development Mac or remote pilot.
The authorized Linux bootstrap remains partial; its measurements and failures
are recorded in EVIDENCE.md. The maintainer's production-performance requirement
and finite repair/optimization backlog are in [ISSUES.md](ISSUES.md). Current
pilot request limits and backoff delays are not accepted production defaults.


## Collector repair contract (2026-10-08)

Hourly admission is a durable deferral, never transport/circuit evidence.
Short redirect-spacing waits release their fetch slot and resume the same chain
outside HTTP deadlines; cancellation cannot leak or double-release a slot.
Connection-pool timeouts are local resource deferrals. Checked
season rows can provide bounded positive episode names/aliases and explicit
language flags; absent flags do not remove releases. Missing, unknown or changed
row evidence retains detail requests. A one-time checkpointed season refresh
accelerates the retained episode backlog. Existing failures/cooldowns survive
upgrade and resume normally. State v4 retains a verified no-overwrite v3 backup.

Scoped HTTP pools keep per-hop DNS validation/pinning and Host/TLS identity;
ordinary requests have no cookie jar. Canonical credentials have separate pools.
Unique non-generic names across the canonical descriptor can prove an episode's
coordinates directly. Conflicting aliases, duplicate keys, native-season splits
and occupied coordinates stay unresolved; source numbering is never evidence.
Reporting distinguishes title discovery, first-pass checks, usable releases,
mappings, failures and unknown languages. A current-queue ETA excludes growth,
retries and enrichment and is withheld while discovery can still expand it.

## October 11 read/publication and language contract

Queries use physical integer joins and independently validated exact recent
release summaries. Targeted native reads avoid recent-index hints and reject
more than 2,000 selected releases before sorting. Empty results from a failed
provider fail explicitly; populated sibling results remain marked partial.
Failed publication retains the last-good pointer and cleans staging. Safe child
reports distinguish enrichment, export, validation, lock and publication, with
bounded reason/exit information instead of arbitrary stderr. SQLite sort scratch
is charged under the existing state/storage budget.

Serienstream Ger-Sub labels and combined English/German season flags establish
German subtitles only. Local resolution selects that positive provider offer
without guessing audio or reusing numeric language IDs across providers.
Explicit unavailable player text retains metadata and previous releases using
v4-compatible fingerprints. Missing language evidence cannot remove releases;
unapproved quarantines remain operator decisions. Changed/missing markup and
interstitial markers retain distinct safe failure reasons. Empty local season
backlog probes are cached for 60 seconds without establishing provider absence.
