# Incremental collection and publication

## Persistent work and bounded execution

Worker state is private SQLite, with one writer and transactional per-title
checkpoints. Persist provider status/last complete listing/last publication/
error/next attempt/failure count; title anchor/path/last listing observation/
last detail check/last semantic change/next due/failure count/fingerprint;
release discovery ledger; mapping inputs hash/version/last check/outcome;
pending revision/publication state. A due queue is a DB query, not a Python
list of the whole catalog. Crash resets expired work leases, not all details.

Provider status enum: bootstrap, healthy, partial, blocked, transport_error,
parser_error, publishing_error, clock_error. Title failures retain previous facts with their
original observed_at; they do not replace success with empty rows. Worker
status is logged locally as bounded JSON; public clients read collection_state
and collection age from signed metadata, never raw error bodies. No public diagnostics service is required.

All following defaults are provisional, executable configuration limits.
One worker config file (JSON, path argument `--config`, unknown keys rejected)
contains `providers` (object mapping provider keys to HTTPS origins),
`canonical_sources` (08), `state_dir`, `output_dir`, `signing_key_file`
(PKCS8 PEM Ed25519), `source_id` (02), `bind_host` (default 0.0.0.0),
`bind_port` (default 8080, range 1–65535), and optional `limits`. All path/source/
provider fields are required, directories must be distinct, key outside output.
The worker key is loaded through cryptography, never a custom PEM parser.
The limit names below are exact; omitted values use defaults. Values must lie
within listed ranges; zero never means unlimited. This single config avoids
dozens of environment variables. Secrets may be referenced by local file path,
never in served JSON. Publish a complete example during implementation.

| Limit key | Default | Allowed range/unit |
| --- | ---: | --- |
| fetch_concurrency | 4 | 1–8 total |
| provider_concurrency | 2 | 1–2 per provider, <= total |
| provider_request_interval_s | 2 | 1–60; start spacing, no bursts |
| provider_requests_per_hour | 1200 | 1–1800; includes retries/redirects |
| body_bytes | 8388608 | 1–16 MiB decoded response |
| request_deadline_s | 30 | 5–60 wall time |
| title_deadline_s | 120 | 30–300 cumulative work slice |
| title_requests_per_slice | 30 | 1–100 |
| ready_queue_size | 32 | 1–128 parsed records/futures total |
| writer_batch_size | 100 | 1–500 rows |
| signal_interval_s | 900 | 300–3600 |
| listing_interval_s | 14400 | 3600–86400 |
| active_interval_s | 14400 | 3600–86400 |
| historical_interval_s | 604800 | 86400–2592000 |
| publish_interval_s | 1800 | 300–3600, only dirty data |
| state_disk_bytes | 20000000000 | 1 GiB–30 GB, subordinate to total |
| public_disk_bytes | 9000000000 | 2 GiB–30 GB, subordinate to total |
| total_disk_bytes | 30000000000 | 4 GiB–30 GB, decimal total including runtime |

Worker container default envelope 2 vCPU/2 GiB, SQLite cache 32 MiB, mmap off,
default four network/parser tasks, one artifact build, one 100-row batch.
Fetch/parser slots and parsed-result reservations are acquired before collection.
One acknowledged writer queue admits complete page checkpoints; producers cannot
reserve their next page before their previous write settles. There is only one
in-flight listing page per provider, with remaining provider slots serving details.
Each durable page is a resumable title slice: redirect request starts, queue wait
and writer work count toward its finite request/time budgets. No entire title is
retained across season/episode pages. Listing row buffers use writer_batch_size;
the complete page/checkpoint transaction remains atomic, including large listing
acceptance. Publication fences only its provider while others keep collecting.
Higher concurrency settings require a corresponding measured container profile;
the 2-GiB promise applies to defaults, not arbitrary overrides.
Parsing a maximum body runs in a supervised child if the adapter cannot
cooperatively stop; 256 MiB per parsing child is included in the container
budget. Writer backpressure stops new tasks. A title with many seasons gets
persisted page/season checkpoints and another slice, not a bigger in-memory
object. Max 100,000 parsed entries per listing page; reject excessive pages,
cap one listing traversal at 100 pages; overflow is unexpected_structure,
never a complete listing or a deletion signal. Detail slices may resume;
listing completeness cannot be fabricated by dropping pages. No response-body
cache after transaction. Raw canonical payloads are bounded temporary data,
not duplicated for each episode or retained as permanent history.

HTTP uses connect=5s, read inactivity=10s, pool=1s within wall deadline; max
2 redirects, validated each time by provider transport. One attempt per due
work item; transport failures reschedule at 5m, 30m, 2h, then 6h (jitter up to
10%, included in next_due). No sleeping retry thread. A 403/positive challenge
opens the provider circuit for 6h, then one half-open request; repeated blocks
double up to 24h. 429 honors Retry-After up to 24h with minimum 1h. Three
transport failures within 5m open a 30m circuit. Parser anomalies wait 24h or
adapter/config repair. These do not affect other providers. Shutdown gives
30 seconds to finish/rollback, then kills/reaps children within 2 seconds.
Never equate future.result timeout with cancellation.

Megakino's observed HTTP bootstrap is an explicit provider capability, not
an arbitrary query/JavaScript facility: GET the original HTTPS path; only when
the complete <=1024-byte observed stub requests exactly `/index.php?yg=token`
and returns to that same path, GET that endpoint and retry the original once.
The three requests and redirects share the caller's deadline, decoded byte and
request-start budgets. Other queries remain rejected. Domain/path/Secure cookie
policy uses the logical HTTPS request URL while connections retain DNS-pinned
IP, Host and TLS SNI. The temporary jar holds <=32 cookies, <=16 Set-Cookie
headers/response and <=8192 cookie-header bytes; cookies never reach a video
host, served artifact, log or persistent worker state. No browser or provider
JavaScript runs. A repeated stub becomes challenge_or_block; a successful HTML
bootstrap establishes transport access only, not language/mapping/media proof.

## Observation, deletion and incremental mapping

Fetch complete lightweight listing, then due title/season/episode pages.
Typed outcomes: ok, not_found, challenge_or_block, rate_limited,
transport_failure, unexpected_structure. A challenge may be HTTP 200;
no-source-found alone is not challenge evidence. Adapter fixtures distinguish
valid empty pages, incomplete paging and block pages.

Listing accepted only if parsing/paging completes and existing count drops
<=10%. A larger drop or any nonempty→empty listing is quarantined for review;
no deletion/publication of that candidate. Equivalent checks apply to title
entity/language collapse. Worker operator can approve an exact quarantined
candidate digest through a local worker command after inspection; no blanket
ignore-anomalies toggle or public admin API. Preserve diagnostic counts and
fixture references, not raw HTML/tokens in public output.

Tombstone a title/entity/language only after absence in 3 successful complete
relevant observations spanning at least 48h. A listing absence must also get
one confirmed detail 404 before title tombstoning; a detail 404 alone still
needs 3 observations/48h. Challenges/failures do not count. For entity/language
removal, complete valid detail enumeration is required. More than 10% removed
at one publication quarantines the diff. Tombstoned items leave active artifact
rows but retain anchors, aliases and first_seen in the worker ledger forever
within the storage cap. At cap, stop admitting new entities/publishing and
alert storage_full; never age out identities to make reappearances look new.
Back up ledger; without it a rebuild cannot promise historical first_seen.

Fingerprint deterministic normalized entity structure/language/path; exclude
check times, host links, tokens and HTML. An unchanged listing does not reset
detail/canonical work. Update last checked on every successful check, but
replace changed semantic rows only. Canonical enrichment uses one bounded
series fetch per refresh. Changed entity/language structure triggers indexed
cache application; changed canonical input/configuration/matcher invalidates
the validated private cache. Recheck active mappings every 7 days,
historical every 30 days, unresolved every 24h; positive source throttling
wins. Worker canonical requests have a separate global budget: concurrency 1,
30 requests/minute, decoded body <=8 MiB, 30s wall/request, at most 4 requests
per title enrichment slice. Retry uses the same failure backoff. TV search uses
the Skyhook term endpoint with title/aliases (maximum two candidate terms);
movie search uses TMDb /3/search/movie with query/year, then unique candidate
details. These worker lookups are enrichment, not user-query telemetry. Persist
compact match outcome and input hash, not upstream JSON blobs.

Matching rules: explicit provider-supplied canonical ID wins after type check;
otherwise unique exact normalized title/alias plus matching known year and
media type may map. Missing year, multiple candidates, conflicting IDs or only
fuzzy similarity stay unresolved. Fuzzy scores can aid review, never automatic
grabs. Episode mapping requires explicit ID, reviewed correspondence, or a
unique exact episode title within the validated canonical title and a season
correspondence already established by explicit source metadata or review.
Unknown season correspondence stays unresolved; ordinal equality cannot establish it. Equal ordinal numbers alone are not evidence, particularly specials.
Canonical season 0 is supported. Publish only the schema's evidence enums;
ambiguous/not_found/conflict remain private diagnostic outcomes. Source rights
filter is applied on export independently of matching confidence.

## Cadence and freshness budget

The accepted 2026-10-01 strategy separates five kinds of work:

- New titles: complete alphabet/listing traversal every4h, with positive title
  hints from the recent page admitted earlier. This traversal owns title absence
  checks; a recent page never does.
- New episodes/languages: AniWorld and s.to `/neue-episoden` polled every15m,
  deduplicated by native episode path and explicit language. Fetch only missing
  title/season parents plus the advertised episode. Existing episodes still need
  their detail page to verify actual positive offers and additions/removals;
  a listing flag alone never creates a release.
- Canonical enrichment: new eligible entities first reuse validated private
  episode-title hints for7d, with original source check/provenance. Require the
  accepted season correspondence and unique exact title; no ordinal mapping.
  A missing eligible hint rechecks the source after30m, at most one series fetch
  per title rather than refetching unchanged payloads for each language. Name,
  year, matcher or source changes invalidate reuse. No raw JSON is retained.
- Historical metadata/removals: pages become reconciliation-eligible after7d.
  Every fifth durable claim reserves history admission; actual reconciliation
  request starts, including redirects, may use at most20% of the hourly cap.
  This is an eligibility interval, **not a promise of a complete7-day sweep**.
  Existing three-complete-observations/48h quarantine/deletion rules still apply.
- Bootstrap/extended outage: bootstrap has its own due pages and is outside
  steady-state latency; recent positive hints may prioritize it. Outages and
  missing signal windows latch degraded coverage while bounded reconciliation
  proceeds. Neither restart nor another overlapping page proves missed history
  was recovered. Ledger identity/first_seen values survive.

Persist origin, last observed window, poll/overlap/unknown counters, due time,
lease, gap_since and <=4096 distinct pending page hints in worker state v3.
Recent parser output is <=512 entries; this is a memory bound, not a claim that
providers expose512 releases. Window replacement and pending admission share
one transaction. Queue overflow rejects the whole observation, retains the old
window and exposes a gap; retry after draining. Page facts and generation-aware
acknowledgement share one checkpoint; concurrent additions cannot be lost.
Pending work/leases and reconciliation start accounting survive crashes.
Private state v1/v2 upgrades are explicit, retain verified no-overwrite original
backups, and do not change public artifact versions or mainline API data.

AniWorld's inspected heading advertises150 entries; the permitted page produced
148 deduplicated episode/language hints. Serienstream's permitted page produced
177. Neither exposes a verified durable sequence or usable pagination. Dates
and ordering are not used as change-log proof. Duplicate/reordered hints do not
reschedule admitted releases. New language gets its own identity. Empty/no-overlap
pages, missed poll intervals (>2 intervals), unknown labels, visible pagination,
origin changes or parse/transport failures latch a coverage gap. Later overlap
never silently clears it. `window-overlap` describes observation continuity only;
it is **not complete change coverage**. Never infer deletion from this window.
Megakino has no verified incremental signal: its inspected sitemap's6073 URLs
point to another origin, timestamps are unsorted and cannot prove freshness.
Do not follow or normalize a foreign origin without an explicit adapter contract.

The six-hour discovery target is conditional on a healthy workload: the change
is exposed on the supported recent page and remains there through a poll; at
most60 changed release variants/15m, <=200 targeted request starts/15m including
parents/retries/redirects, <=100 complete listing pages/4h, existing provider
availability, valid supported markup, and canonical metadata with accepted
season correspondence when canonical discovery is claimed. Four signal polls,
<=800 targeted starts, <=25 amortized listing starts and <=240 reconciliation
starts/hour leave headroom below1200/hour. All requests retain2s start spacing.
An actual full100-page traversal costs up to200s from spacing alone; not every
hour necessarily uses the amortized budget. Measure bursts, cumulative due age
and shared canonical/publication/consumer admission; arithmetic is not a pass.

Stage budgets for a recent-visible change:15m poll +45m bounded collection and
canonical admission +30m publication +30m consumer poll +15m shaped transfer/
validation. A title visible only on the complete listing retains4h listing +
the same45m/30m/30m/15m budgets (6h total). Unknown year/correspondence, burst
window overflow, source blocks or queue backlog are degraded/unresolved cases,
not a healthy-workload guarantee. Keep actual observation→publication→installation
timestamps separate from simulated-clock scheduling and observed live markup.
The original1050000-page full-active sweep failure remains a capacity bound.
At240 historical starts/hour even1.1m stored pages need at least4583h (~191d)
for one sweep, before other constraints. Report actual progress and no-starvation;
do not label such history reconciled in7d. M5 remains closed pending measured
coverage, retention economics and operating approval.

## Discovery and publication

On first valid observation, insert release_id/first_seen_at in the same DB
transaction as its positive language evidence. Upserts/rebuilds/corrections
and temporary disappearances preserve it. New language gets a distinct release.
Use worker wall time with a persisted clock watermark: backwards jumps >300s
pause collection/publication as clock_error until repaired; within that skew,
clamp an existing release observation to its previous observed_at. Never move
first_seen forward on conflict. Bootstrap uses actual observation time (not airdate); mark bootstrap status
locally and expect a finite back-catalog burst in recent RSS, handled by *arr
monitoring rules. Do not rewrite dates to suppress it. A restored worker uses
its ledger; a newly self-hosted source has its own initial discovery history.

Build from one consistent read snapshot. Copy only allowlisted fields, verify
DDL/counts/paths/IDs/FKs/integrity and anomaly thresholds, close/checkpoint and
compress. No private rows, raw HTML, media URLs, cookies, auth, artwork or
unreviewed canonical payloads. Artifact limits and signing/retention are in 02.
`publication_sources` is an explicit bounded list of cleared provenance labels,
empty by default, independent of collector configuration/credentials. Tests use
only `synthetic-v1`. No real-source/public distribution clearance is inferred.
The selected bulk export uses one read-only attached ledger snapshot and fixed
integer-key joins. Parent uniqueness stays live; deferred secondary indexes are
restored before exact validation. The recent-release index stays interleaved
during insertion: moving its duplicate IDs outside the zstd window failed the
full compressed cap. The full publication supervisor allows360s after measured
195–214s successful builds; its 120s validator, memory/byte/rate limits and
30-minute cadence remain unchanged. Earlier 180s failures remain recorded.
Publish dirty data at most every 30m, renew metadata every 24h using identical
artifact bytes if unchanged. A failed export leaves old pointer active.

When blocked, retain last good observations and renew distribution metadata
with original collection age. Logs include provider/stage/outcome/count/duration,
not queries, credentials or video URLs. Defaults: five 10-MiB rotated local log
files, no per-response/body history. State disk pressure stops scheduling before
free space drops below 512 MiB; active transactions roll back on disk errors.

## Bounded total storage and two-snapshot retention (2026-10-02)

The maintainer's budget is approximately **30 GB total**, conservatively fixed
at30,000,000,000 bytes. State defaults20,000,000,000 and output9,000,000,000;
reserve1,000,000,000 for the installed image/config/key and bounded runtime logs.
Quota sums must fit that budget; no oversized opt-in profile remains. Before
collection, startup migration and publication, account for all files under
state/output (including WAL/SHM, logs, backup copies and staging). Count the
larger logical/allocated size and deduplicate hard links. Linux /proc also counts unlinked open SQLite
sort files; export temporary files stay under managed build staging. Report managed used,
reserved runtime, total used/quota and free bytes, with80% warnings.

State admission retains512MiB for bounded checkpoint/metadata writes. One
published artifact build reserves1GiB SQLite+256MiB compressed+64KiB metadata
under the output and total cap. No memory, artifact, provider-request or consumer
limit changes. Actual backing storage must be available; statfs cannot establish
thin-provisioned physical capacity. An image/runtime exceeding the1-GB allowance
is outside this profile and must be measured before use, without silently raising
the total cap. Container daemon stdout logs must be bounded too.

Retain current plus one previous distinct artifact per provider (two **total**,
not two per schema), their needed manifests, and active bounded HTTP transfers.
At startup, after successful publication and before the next build, clean obsolete unleased
owned protocol files. Directory locks serialize descriptor acquisition/unlink;
serve the leased descriptor rather than reopen its pathname. Keep only the two
referenced private publication rows; burned revision floor remains independent.
Publication history does not retain full catalog generations. Crash-pending
current bookkeeping is repaired from its already-durable envelope before pruning.
Schema/key validation and consumer last-good survive missing remote generations;
bounded refreshed-pointer recovery and cache policies are owned by02.

Preserve compact first_seen/identity/discovery, mapping provenance, current
records and resumable crawl/signal checkpoints. Recognized private-state migration
backups remain no-overwrite and counted, with the exact missing backup size
reserved before startup writes. Before quota admission, collect only abandoned reserved private parse/create/backup
scratch and public build directories after ownership locks. Read-only preflight
and cleanup can remove obsolete prior72-hour output even if its old byte usage
exceeds the new quota; they do not mutate the private DB. This policy never silently deletes an existing
verified backup or released-mainline user state. Multiple old full migration
backups can exceed the state/total budget; report storage_full and explicitly
archive an obsolete backup offline before resuming, rather than retain catalog
history or increase disk limits. No new periodic full-ledger backup series.

Measured full-artifact257838610 bytes ×six current/previous copies is1.547GB.
Measured private ledger2702184448 ×six live/one-backup copies is16.213GB;
three live ledgers alone8.107GB. Add at most16 active older artifacts at the
unchanged producer256-MiB cap (4.295GB), one1.342GB staging reserve,52.4MB
rotated logs and1GB runtime allowance: derived bound24.449GB before ordinary
state growth/headroom. Two legacy full backups per provider alone bring state
to24.320GB and exceed its default quota; they are not hidden or deleted.
Actual full-cardinality footprint/retention experiments are recorded in10,
with replica pressure distinguished from live all-provider publication.
The original100×257838610=25.8GB/20-GiB failure and rejected576-GiB profile stay
historical in11; neither is relabelled as a passing experiment.

Truthful positive episode checks update observed_at; complete unchanged listing
checks update listing_checked_at. Both dirty artifact bytes. A metadata renewal
without collection reuses identical bytes and original timestamps. One changed
episode still creates a full snapshot; no timestamps or validators are weakened
for deduplication.

Transfer cost remains a product constraint. The measured artifact ×48 distinct
snapshots/day is12.376GB/client/provider/day, or37.129GB for3 such providers.
At100/1000/10000 clients this is3.713/37.129/371.288TB/day before protocol traffic.
The measured281.548s shaped install ×144 is11.26h/day of serial installation.
These are bounds derived from an actual artifact/run, not observed live change
rates, invoice prices or a sustained result. Even sparse changes or background
rechecks can reach this churn. Present measured operating cost before proposing
deltas, shards or another protocol; none is introduced here. M5 remains closed.

Under a full stored-history backlog, reserved reconciliation keeps observing
metadata during each30m publication interval. With truthful observed_at changes,
this predicts48 distinct full snapshots/day even when new releases are sparse.
Thus the37.129GB/client/day three-provider model is also the selected full-size
steady reconciliation scenario, not merely an adversarial all-release-change
burst. It remains a derived scenario (observed dirty behavior plus measured
artifact size), not live cadence or accepted public operating economics.

Megakino's supplied movie markup exposes country/year/runtime together in
`div.pmovie__year`. Accept only the same-origin
`a[href="/xfsearch/release_date/YYYY/"]` within that one closed scope, with
matching four-digit visible text. A URL alone, generic year text, site-wide
language or country/runtime is not evidence. Reject conflicting/duplicate/
foreign/unclosed year metadata. Compare a title/year canonical search binding
against independently fetched details; a contradictory detail title/year stays
unresolved. An explicit verified IMDb binding retains its stronger ID check.

### Measured sparse transfer cost (2026-10-03 refinement)

See10/11 for six fresh exports at50k/1m/2m+240, including timestamps and60 new
language releases. Unchanged bytes are identical; truthful listing/observation/
canonical renewal dirties snapshots. Full compressed size is257.891 MB.
Fresh compact-key/index churn makes60 additions change177,309 pages; offline
1-MiB chunk reuse still transfers176.783 MB.256-KiB independent chunks exceed
the existing bootstrap artifact cap. This supersedes the older artifact-size
model above:48 changes/day across three providers derive37.136GB/client/day.
Identical signed renewal now transfers no consumer artifact body.

Recommend a measured stable-key/bounded delta experiment before any distribution
redesign. Publication coalescing to1h alone halves the cost but still exceeds
18.5GB/client/day in that scenario; its latency needs explicit remeasurement.
No protocol, six-hour target, timestamps or30-GB worker budget changes here.
