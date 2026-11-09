# Catalog query implementation contract

## Service boundaries

The worker owns provider observations, durable queues/checkpoints, canonical
evidence and publication. Its separate read command answers authenticated
`POST /catalog/v1/query` from immutable allowlisted catalogs. It imports no
FastAPI application globals and never scrapes or extracts media during a query.

Local AniBridge owns corrections, filtering, Torznab, accepted job identities,
media resolution and output publication. `CATALOG_MODE` defaults to `legacy`;
`query` explicitly selects metadata API search. Legacy query-time provider
scraping is deprecated and may be removed in a future release. Query mode uses
collected metadata, so freshness and mapping quality affect results; search work
moves to the collector while media downloads remain local. Opt-in routing does
not disable additive private database migrations. Use [identity.md](identity.md)
for source identity, language and magnet compatibility rules.

Query mode requires an HTTPS origin root (`CATALOG_API_URL`), a source ID
(`CATALOG_SOURCE_ID`), and exactly one bearer credential source
(`CATALOG_API_TOKEN` or `CATALOG_API_TOKEN_FILE`, whose path is inside the API
container). `CATALOG_ALLOW_PRIVATE_HTTP` defaults false; true permits unencrypted
non-loopback HTTP for trusted-network testing and does not enforce private IP
addresses. Loopback HTTP remains allowed.
The complete query configuration is mandatory. Legacy mode must reject source
settings rather than ignore them. Existing `CATALOG_CONFIG_FILE` JSON remains
supported, but nonempty environment catalog settings cannot be mixed with it.
No API endpoint is preset; the Oracle-hosted endpoint is private testing only.

Filmo movie collection and grabs are an explicit query-mode extension, not a
rename/removal of Megakino or a legacy query-time scraper. Each native source
choice has its own stable release identity and frozen selection descriptor.
Declared quality/audio/subtitle metadata remains separate from measured media
properties. Conflicting claims remain visible without selecting a convenient
resolution/source. Generic WEB, unknown sources and incomplete quality claims
stay in RSS attributes/descriptions; *arr release titles omit them because bare
resolution tokens can falsely imply HDTV and WEB cannot prove WEB-DL/WEBRip.
The collector never mints player tokens; accepted local grabs
refetch their exact offer and use bounded session/CSRF handoffs to VOE or Byse.
Other hosts remain observed catalog data but are withheld from automatic client
results. The optional Filmo host filter applies before totals and pagination.

## Collection and correspondence

Persist inventory, title, season and episode work across restarts. Recent feeds
are capped hints, not lossless change streams. Inventory refresh, feed retries
and historical reconciliation have independent durable eligibility. Local budget
or connection-pool waits are deferrals; HTTP failures, parse gaps and explicit
provider unavailability retain distinct reasons. None implies a provider ban
without supporting evidence.

Keep source titles/native coordinates and positive language observations.
Missing language/host markup and empty provider templates are parse gaps; they
cannot withdraw previously valid offers or satisfy outstanding detail retries.
Only explicit upstream negative evidence may mark an offer set unavailable.
Observation failures, retry receipts and signal acknowledgements share one
transaction. Unexpected writer termination must stop waiting producers.
Complete season evidence can settle recent-feed obligations without postponing
unresolved detail retries. Repeated successful pages missing an advertised
language retain the obligation with increasing retry delays capped at one hour.

Canonical parent and episode identities require verified provenance. Unique,
non-generic names may establish correspondence; similarity and equal numbering
alone may not. Duplicate names, conflicting IDs, different cuts and ambiguous
season relationships remain unresolved. Local corrections take precedence.
Validate cached descriptors as strictly as fresh input. Acquisition failures,
negative results, unchanged receipts and local rematching remain separate paths;
due retries cannot be skipped merely because an older descriptor was cached.

Normal maintenance polls recent TV feeds, refreshes inventories and reserves
bounded historical work. Eligibility targets are not freshness guarantees.
Request admission is a configured local budget, not an upstream quota. Movie
and optional-provider support requires explicit adapter/language evidence.

## Publication and queries

Private state v7 adds bounded per-work failure receipts; public read schema2
remains independent. Collection records journal generations transactionally.

New Filmo ledgers use private v8 and publish schema3/identity2. Existing provider
ledgers stay v7 and their public schema1/2 and magnet v2 compatibility remains.
Schema3 adds nullable release variant anchor/metadata columns; Filmo requires
both, with allowlisted metadata bounded to 4 KiB. No player URL, token or cookie
is published. Filmo currently uses full export and full validation; existing
schema2 partition/proof reuse is not automatically extended to schema3.
Export uses a consistent SQLite snapshot, validates staging and atomically
switches the provider pointer under the read lease. Acknowledgement removes only
captured generations, leaving later writes pending. Proof reuse requires a
verified compatible base; invalid bases force complete validation.

Failed/cancelled publication retains the last-good catalog. Providers own
separate pointers, failures and revisions. Readers pin each response; cached
pages and multi-page reads must agree on revision. Rebuilds preserve release
identity/first-seen, accepted maps, corrections and durable maintenance state.

Queries cover title/ID discovery, native-title batches and recent releases.
Local corrections are applied before canonical/language/category/mode filtering,
exact totals and final pagination. Targeted retrieval retains older releases;
recent feeds apply their own age window. Large titles use bounded pages, never
per-episode network calls. Broad queries fail explicitly instead of truncating
totals. Partial provider results identify the missing provider; a failed empty
query must not become a successful empty result.

Current finite bounds include eight active queries, 16-KiB requests, 2-MiB
responses, 200 candidate titles, 500 native releases/page and 2,000 native
releases/provider/search. RSS pages cap at 100, offset at 10,000. Cooperative
SQL/HTTP/local-search budgets are 2/3/15 seconds. Cancellation keeps admission
occupied until the underlying reader settles. Cross-request recent pages can
straddle updates; callers overlap polls and deduplicate stable GUIDs.

The bounded local cache keys origin, source, credential fingerprint, protocol
and full request. It validates every hit, coalesces misses, retains revision
floors and permits positive stale results only within the configured window for
eligible transport/service outages. Authentication/contract/replay failures and
cold outages fail explicitly. Negative cache entries do not hide outages.

## Jobs, security and recovery

Admission freezes source identity, native coordinates, language and canonical
label. Durable jobs survive metadata outages/replacement and expose truthful
progress, completion and output availability. Unknown transfer sizes stay unknown;
no premature 100% or automatic duplicate acquisition after import/file movement.
Legacy aliases, jobs, categories and path translation remain compatible.

Selected HLS tracks may use estimated byte totals from a bounded finite-playlist
and first-segment HEAD preflight. Estimates use evidence from each selected track,
remain labelled as estimates, and are replaced by measured lengths as transfer
finishes. Missing metadata retains unknown totals; video bytes alone cannot stand
in for an unknown audio track. Radarr requires a nonzero total to display progress.
Logs distinguish legacy history from catalog jobs and report downloaded bytes,
size basis and output availability. Supervised child failures retain only bounded
reason/stage/exit diagnostics, never raw stderr, media URLs or release names.
Transient SQLite busy/locked errors while saving progress retry the latest
snapshot without stopping the transfer. Other parent failures retain the
exception class and operation. A missing child progress snapshot leaves the
last known phase and its deadline intact; completion still requires a readable
terminal receipt. These diagnostics do not establish the cause of older
failures that did not record them.

Removing an unfinished request and re-adding it after alias removal settles may
queue a new generation of the same frozen request. Pending removals and remaining
cancelled aliases return a conflict. Previously published requests stay protected
from automatic acquisition even if their output was subsequently moved.

Filmo remuxing retains embedded tracks and their language tags. Separate HLS
audio binds each declared language to an exact rendition URI in the selected
video's group. Known Byse SRT/WebVTT and HLS WebVTT captions use verified,
bounded acquisition and a local track manifest, then remux to Matroska with
explicit language tags. External-rendition limits are eight tracks per kind and
sixteen total inputs; direct captions are capped at 2 MiB each. Ambiguous or
unsupported layouts fail explicitly. Generic provider subtitle labels do not
prove soft versus burned-in captions. STRM playback still depends on the player.

Query-mode qBittorrent forms accept URL-encoded and multipart text fields.
Admission bounds total bytes, receive frames, elapsed time and field counts;
files, duplicate fields, incomplete multipart and blank pause values are rejected
before job creation. This includes the multipart form *arr uses for long magnets.

Metadata uses an explicitly selected verified HTTPS origin and bearer file;
private HTTP requires the documented opt-in. Redirect/DNS/TLS, response decoding
and child resource limits remain enforced. No credential, raw query, IP, player
URL or arbitrary child stderr belongs in diagnostic output. Proxies/operators
can still observe requests; disabled access logging is not end-to-end privacy.
Optional qBittorrent session authentication protects `/api/v2`; it is not an
all-router public security boundary. See the API environment example and
[security guidance](../../agents/security-legal.md).

Writable state must enforce process-lock exclusion. Preserve every backup
generation and `/state/backup`. SQLite backups must include committed WAL; do
not copy only an active main file or open active WAL state as immutable.
Admit live state, copies, backups, staging, images/logs and the 1-GB reserve under
the 30,000,000,000-byte aggregate budget before a workload. Unknown storage usage
refuses admission. Collector baseline is 2 CPU/2 GiB; serving has a separate
budget. Those allocations do not establish sustained capacity.

Worker v6→v7 migration creates a no-overwrite backup. Rollback uses the candidate
tooling while stopped and preserves newer observations; restoring yesterday's
ledger is not a state-preserving code rollback. API restoration must also retain
jobs/files and its authentication boundary. Follow the
[version-specific update guide](../../../scripts/catalog/query_pilot/WORKER_UPDATES.md).
Open acceptance and release decisions are maintained in [ISSUES.md](ISSUES.md).
