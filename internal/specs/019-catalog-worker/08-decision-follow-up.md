# Local jobs, estimates, canonical fallback and management

Accepted on 2026-09-26: nonblocking scoped quality sampling, bounded canonical
ID-miss lookup, durable blocked jobs and authenticated local HTTP management.
The earlier whole-show sampling/TV-720p proposal was rejected: one season,
language, host or adaptive variant cannot establish another's quality. Snapshot
size concerns did not authorize remote search. These contracts close the former
follow-up questions; no WebUI, browser/CAPTCHA solver or hosted mutation API.

## Quality sampling

Use observations from actual local downloads first. An explicit title/ID search
may enqueue at most one missing eligible scope from its first ranked result;
queryless RSS, caps, broad empty searches and catalog updates enqueue none.
Scope key = provider + title_id + native season (null for movie) + language +
SHA-256 of host-selection policy/configured origin + scope structure fingerprint.
The latter hashes sorted (entity_id,path,language) rows in that title/season/
language scope, not the requested episode alone, so reuse is actually scoped.
A scope records sampled entity ID, host ID, selected variant fingerprint,
height, codec (sampled entity only), measured_at, expires_at and outcome.
Keep signed/media URLs only in memory. Public catalog receives none of it.

Default queue 32, one running sample, at most 6 starts/hour, deduplicated by
scope across queued/running/cooldown work. Queued optional work expires after
10 minutes and may be dropped on restart; retained cache/cooldown is durable.
Queue full drops the optional sample,
never fails or delays search. Success TTL 24h, failure cooldown 6h, challenge
cooldown 24h; no immediate retries. Max 10,000 private cache rows, evict expired
then LRU; count includes failures. New sampled-entity path, origin, language,
host policy or extractor version invalidates the scope; a mapping/title edit
alone does not. Changed host choice invalidates inherited evidence. Only exact
scope inherits height with provenance estimated; not codec/size. TTL is not
proof that an unchanged path still serves the same file.

Conflicting height, host or selected variant observations within the same
retained scope suppress inheritance. The latest measured entity keeps its exact
height/codec; unmeasured siblings stay unknown. Suppression persists through
restart and subsequent matching observations for that cache lifetime. Evidence
outside the configured host policy is rejected; damaged optional records cannot
fail search or stop the estimate queue. This conservative refinement introduces
no extra probes and changes no release identity or artifact field.

Overall sample budget 20s (config bounds in 04), 16 MiB total fetched bytes,
8 requests including redirects/manifests, 64 KiB stdout/stderr each. Use a
supervised process for blocking upstream extraction. At deadline/cancellation
close network responses, terminate process group, kill/reap within 2s. Never
run unbounded yt-dlp/ffprobe nested HTTP requests: use verified bounded
transport to fetch permitted metadata/byte ranges into temporary local files;
ffprobe gets local input and network protocols disabled. If a format requires
unbounded segments or cannot be inspected within those constraints, return
unknown. No private HTTP proxy service is introduced. Process RLIMIT/cgroup
memory <=256 MiB and one child count toward the consumer's 1-GiB budget.
FFmpeg I/O timeout/probesize/analyzeduration alone are not wall deadlines.
Search never awaits sample execution or completion. Defer samples when a
download or update-validation child is running. Across downloads/validation/
probes, admit at most two children and <=512 MiB total child memory budget;
validation and sampling each use <=256 MiB, downloads <=256 MiB each. Optional
work yields to grabs; updates may wait and must report freshness budget misses.
Bound stdout/stderr for resolution/download workers to 64 KiB each as well.

## Canonical source adapters and ID misses

Local validated mappings and overrides are checked first. Only an ID-bearing
miss may use the configured canonical source; never send q or an ID to the
catalog worker. `canonical_sources` config object has `tv` = `skyhook` or `off`
(default skyhook to preserve the existing TV dependency), `movie` = `tmdb` or
`off` (default off), and optional `tmdb_token_file` required for tmdb. Endpoints
are adapter constants, not user input URLs. TMDb credentials use the Bearer
Authorization header, never query strings. Worker uses the same source config;
source access/redistribution approval remains separate. A private mapping
implementation can use fixtures before credentials/rights are available.

TV: TVDB positive decimal lookup via Skyhook `/v1/tvdb/shows/en/{id}`; TMDb-TV
or IMDb may use `/v1/tvdb/search/en/?term=tmdb:{id}` or `imdb:{id}` then one
show lookup. Match the returned external IDs exactly, never take first result.
Hosts are fixed HTTPS skyhook.sonarr.tv and api.themoviedb.org, respectively;
verified public-address transport and TLS apply. Movie: TMDb `/3/movie/{id}` or `/3/find/{imdbid}?external_source=imdb_id`;
require unique movie result/exact ID. An IMDb find may use the remaining
request for movie details to validate other supplied IDs. Do not route movie IDs through TV search.
Namespaced IDs are `tvdb`, `tmdb-tv`, `tmdb-movie`, `imdb`; rid/tvmaze are
unsupported and not advertised. tmdbid namespace follows request media kind.
Conflicting supplied IDs stop unresolved before fallback; fallback must validate
all supplied IDs, no cascading source guesses.

Budget per request including cache wait: 2s wall, at most 2 HTTP requests,
no retry, connect <=0.5s, read <=remaining budget, maximum 2 MiB decoded total,
no redirects. Global max 2 in flight and 30 lookups/minute; no waiting queue
when exhausted (503 transient). Singleflight wait shares the 2s budget.
Cache compact IDs/title aliases/type/year only in private DB, max 1000 entries
and 16 MiB; positive TTL 24h, negative/ambiguous 15m, transient failure 60s.
Key includes source config fingerprint, namespace and ID. Cache eviction is
expired then LRU. No raw source payload or per-query telemetry log.

Use exact unique title/alias, compatible type/year and returned IDs to identify
local candidates. More than one same-provider candidate stays unresolved;
same canonical title on multiple providers is valid. This fallback discovers
candidates, **does not compute episode correspondences during search**. Only
existing validated/local episode maps may answer canonical episode queries.
Successful no-match/ambiguity/missing-map returns empty RSS + unresolved;
transport/rate/deadline returns 503 when the lookup is necessary. Disabled
source yields unresolved, no network. Publish ID capabilities only for adapter
support actually tested; deployment without a movie source may still answer
published/local movie ID hits. Worker enrichment can eventually resolve misses;
there is no demand signal to the hosted worker.

## Durable grab/job contract

Single private-DB transaction creates frozen request, Job (paused when the add form requests paused), submitted-hash
ClientTask/alias and durable queue admission before `/torrents/add` returns
HTTP 200 `Ok.`. Repeat identical add is idempotent, including paused state;
never reschedules a duplicate. Validate language/path/provider/mode, hash,
configured save-path containment and catalog mapping conflicts without provider
network. Malformed=400, disabled/unauthorized provider=403, identity conflict=409,
queue full=503 with Retry-After 60. Preserve existing qBittorrent auth contract;
management auth is separate, and deployments must protect the compatibility
surface with existing network/ingress controls. This task does not retrofit
qBittorrent credentials or treat the fixed SID as secure authorization.

Frozen request includes identity/payload from 09, submitted hash, original
label, canonical selection/provenance, host preference, source path, requested
mode, category/save path, and attempt generation. Catalog changes cannot remap
it. Existing jobs remain viewable/cancellable if a provider is disabled;
execution pauses with disabled_provider until re-enabled and explicitly resumed.
Batch add accepts at most 10 nonempty magnet lines in a 128-KiB form body;
validate and commit all atomically or return an error with none admitted.
Never silently process only the first line as mainline currently does.
One scheduler service owns management and qBittorrent transitions. DB leases
and compare-and-swap version/generation prevent double execution and stale
completion callbacks. Admission cap 1000 queued/running/paused/retry/blocked
jobs; failed/completed/cancelled records retained, bounded by private disk.
Default private metadata admission ceiling 16 GiB (existing DB plus new state);
use `limits.private_metadata_bytes` in 04 to tune it. At that ceiling or private
disk free <512 MiB reject new admission and retain old records. Existing upgraded
state above the ceiling stays readable and is never automatically pruned.
Media files remain under existing download/storage settings; cap checks must
account for their shared filesystem free space.

| Internal state | qBittorrent state | Transition |
| --- | --- | --- |
| queued | queuedDL | scheduler claims lease → resolving |
| resolving | metaDL | resolved → downloading, classified failure below |
| downloading | downloading | committed verified output → completed |
| retry_wait | queuedDL | due time → queued; no sleeping thread |
| paused | pausedDL | explicit resume → queued (or prior blocked/failed state) |
| blocked | stalledDL | explicit retry → queued; no automatic challenge loop |
| failed | error | explicit retry → queued when source/config repaired |
| cancelling | pausedDL | stop/reap and commit → cancelled |
| cancelled | pausedDL | retained; no implicit resume, explicit removal allowed |
| completed | pausedUP | files/STRM published and durable; only then progress=1 |

qBittorrent progress is 0..1; internal historical progress 0..100 is converted.
Blocked/failed/retry states retain actual partial bytes but never progress=1,
completion_on or completed content path. Inactive speed=0, ETA=8640000 when
unknown; total size=0 until known. `/info`, `/sync/maindata`, `/files` and
`/properties` share one projection; files endpoint contains only actual files.
Completed STRM means durable STRM file, not proven playback or Sonarr import.
Freeze direct/proxy delivery with the accepted local request. Proxy completion
must atomically retain playback registration bound to that request: an imported
STRM copy outlives download-client alias/original-output removal, preserving the
mainline separation between stream mapping and download history. Subsequent
provider disabling or STRM secret rotation governs playback access. Scope new
catalog tokens so a signed nested URL cannot be reused on a legacy arbitrary-URL
route. These private implementation refinements do not change public identities
or infer import/playback from file creation.
Sonarr source inspection maps stalledDL to warning, pausedDL to paused and
pausedUP to completed; actual client behavior remains gate C5, including
Radarr and completed-download removal. No automatic replacement claim.

Transient source failure: 3 attempts total, retry waits 1m then 5m; exhausted
→ failed with retry_exhausted. Positive challenge→blocked immediately, no retry
time. Confirmed 404/unavailable→failed unavailable; parse/no-source→failed
extraction_error, not CAPTCHA. Local provider circuit wins over job timing.
Resolution deadline 60s total/16 requests/16 MiB, maximum 3 host choices,
all within that budget, same transport cancellation as sampling. Download
itself is streaming, inactivity timeout 120s, bounded by existing concurrency
and configured bandwidth/storage; no sample byte cap on an authorized download.
Max 2 concurrent downloads in the 1-GiB profile, each supervised; no new
unbounded in-memory buffering. Full download may take hours: progress heartbeat
renews a 60s lease every 10s, and shutdown/pause/cancel must terminate I/O and
children within 5s. A resolution attempt starts when its lease is claimed; restart consumes the
interrupted attempt and schedules the next, or fails retry_exhausted.
Partial files kept for supported resume, never published
as completed; restart requeues expired resolving/downloading leases with their
frozen request, preserves attempt budget and partial-file validation. Missing
completed output becomes failed/missing_output, never auto-downloads silently.

Implement POST /api/v2/torrents/pause and /resume (form hashes, pipe-separated
or all) using this service; cap explicit hashes at 100, process all in DB batches
for all, no network in handlers. Return Ok. after durable desired-state commit.
Pause on completed is a no-op; resume on completed/cancelled is a no-op.
Pause persists desired state before stopping I/O; completion CAS loses to pause
or cancel, so it cannot resurrect the job. Resume does not clear a blocked or
failed reason: return it to its prior state; retry is explicit. Retry increments
attempt generation, resets attempt budget, retains identity/partial bytes and
clears error; at most one retry/60s/job. Cancellation is idempotent, preserves
files/history, and takes precedence over late callbacks. qBittorrent delete
cancels/releases the last alias before applying its explicit deleteFiles plus
existing local deletion policy; path containment is rechecked. Restart leaves
paused/blocked/cancelled/failed untouched, and never deletes them by age.

## Management HTTP contract

All routes below use `Authorization: Bearer <MANAGEMENT_API_TOKEN>`, minimum
32 random bytes encoded base64url, constant-time comparison, no query token,
fixed SID or indexer-key equivalence. Absent token → 503 management_disabled;
wrong/missing →401 plus WWW-Authenticate. Provision with local secret/env,
rotate by replacing and restarting; never echo token. No CORS by default;
configured exact origins only, reject nonallowlisted Origin on mutations.
No cookies; future cookie UI requires separate CSRF design. TLS at nonlocal
exposure. Request body <=16 KiB, 60 mutations/minute/token, 429/Retry-After 60.
All JSON timestamps Unix seconds; unknown keys rejected, IDs/coordinates as 09.

Common error: `{"error":{"code":"version_conflict","message":"Resource changed",
"retryable":false}}`. Standard codes: 400 invalid_request, 401 unauthorized,
403 refresh_disabled, 404 not_found, 409 conflict/invalid_state,
412 version_conflict, 422 validation_error, 428 precondition_required,
429 rate_limited, 503 queue_full/storage_full/management_disabled.
No raw upstream errors/URLs. All resources expose integer version starting 1,
ETag `"{version}"`; PATCH/DELETE/job actions require exact If-Match, atomic CAS.
Repeat cancel on an already cancelled version returns 200 without increment.
Creates accept required Idempotency-Key (UUID): same body returns same resource,
different body=409; keys retained 24h, max 10,000, capacity full=503.

| Method/path | Request and successful response |
| --- | --- |
| GET /api/v1/catalog/status | 200 `{providers:[{provider,readiness,source_id,configured_source_id,revision,accepted_revision,hold_revision,collection_state,activated_at,listing_checked_at,oldest_active_check_at,metadata_expires_at,coverage,counts,update_state,last_error}],version}`; absent fields null; provider readiness ready when detail/mapping coverage complete, partial when an artifact exists with coverage gaps, not_ready when no usable artifact exists; update_state idle/checking/downloading/validating/error/switching |
| GET /api/v1/catalog/overrides | filters provider/entity_id; limit 1–100 default 50, offset 0–10000; 200 `{items,total,offset,limit}`, ordered id ASC |
| POST /api/v1/catalog/overrides | `{provider,entity_kind,title_id,entity_id,target:{namespace,external_id,season,episode},reason,enabled}` →201 resource + Location |
| PATCH /api/v1/catalog/overrides/{id} | subset of target/reason/enabled →200 resource; identity immutable |
| DELETE /api/v1/catalog/overrides/{id} | no body →204, missing=404 |
| POST /api/v1/catalog/refreshes | `{provider,title_ids:[id]}` (1–10 existing IDs) →202 task + Location; equivalent active sorted set deduplicated |
| GET /api/v1/catalog/refreshes/{id} | 200 task |
| POST /api/v1/catalog/rollbacks | `{provider,revision,source_id}` →202 task, only retained previously accepted version; uses status If-Match plus Idempotency-Key |
| GET /api/v1/catalog/rollbacks/{id} | 200 task |
| GET /api/v1/jobs/{id} | 200 job |
| POST /api/v1/jobs/{id}/retry | `{}` →202 job; only blocked/failed, not legacy_request_incomplete |
| POST /api/v1/jobs/{id}/cancel | `{}` →202 cancelling or 200 cancelled |

Status exposes the active `source_id` separately from `configured_source_id`.
While retaining a prior source, idle update status becomes `switching`; an
in-progress attempt or error retains its own state. Configuration pin changes
advance the status version. This supplies the two provenances required by 02
without discarding a last-good catalog during a source change.

Override entity_kind accepts title/episode/movie. title has entity_id=null,
coordinates null; episode requires
entity_id belonging to title, season>=0/episode>=1; movie requires the movie entity_id and uses its title target with
null coordinates. reason nonempty <=1000 UTF-8 bytes, enabled boolean.
Title override changes suspend incompatible existing episode overrides until
corrected; an episode override requires a consistent enabled/published title map.
Resource adds UUID id, version, created_at, updated_at, provenance=local_operator,
status=active/disabled/conflict and conflict_reason nullable. Never fetch external
URLs during override write. Enforce one enabled override per identity/namespace;
unknown target identity=422, conflicting canonical assignment=409. Nonempty
reason is the operator's assertion, not automated mapping evidence.

Task shape `{id,type,state,version,created_at,updated_at,provider,title_ids,
request,result,error,next_retry_at}` with type refresh/rollback, state queued/running/
succeeded/partial/failed/cancelled, result null or `{changed,unchanged,failed}`
integer counts, error null or the inner `{code,message,retryable}` object;
request stores the validated create body, rollback uses empty title_ids.
Durable queue default 32, concurrency 1, active equivalent dedup; refresh task
max 10 titles, 120s each, total 1200s, restart resumes completed-title checkpoints.
Failed/finished tasks retained 7 days, maximum 1000; prune finished oldest only.
Rollback task uses 02 transaction and preserves accepted floor; no network.

Job shape `{id,version,state,release_id,hashes,provider,mode,progress,
attempt_count,created_at,updated_at,last_attempt_at,next_retry_at,error,
actions}`; progress 0..1, actions subset retry/cancel/pause/resume/remove based
on state. In this milestone management actions list only retry/cancel;
qBittorrent handles pause/resume/delete through the same service. Future
management-authenticated UI adapters must reuse that service. Legacy job
release_id/mode may be null; return the inner error object from the common
error contract, never fail serialization of a preserved legacy job.

All POST creates return only after durable commit, never after external work.
Read list/status snapshots are internally consistent. Tests cover concurrent
PATCH/retry/cancel, duplicate requests after lost response, restart of tasks,
stale ETags, queue/disk limits, invalid path/namespace and token redaction.
