# Services, distribution and activation

Normative v1 design. [Schema and identities](09-artifact-schema-and-identities.md)
owns the wire database; this document owns trust and activation. Numeric limits
are provisional engineering defaults to validate, not benchmark results.

## Boundaries and packaging

Use Python 3.14, separate `apps/catalog-worker/` and `apps/api/` images and
state volumes, and `packages/catalog-core/` for records, normalization and
validation. Core cannot import API config, routes, engine or worker state.
Start source adapters worker-local, extracting a shared package only when a
second real caller needs it. Inject transport/config; preserve upstream state
under `ANIWORLD_INSTALL_FOLDER`, never change HOME.

Use separate uv projects initially; build a versioned core wheel and install
that same wheel into both images from repository-root build context. Record
its exact version/hash in each build. Do not require a root-workspace/lock
migration for this feature. Gate C0 verifies installed wheels, Docker and
PyInstaller packaging; later workspace conversion is separate work.

Reuse SQLite, HTTPX/AnyIO and Python 3.14 `compression.zstd`. Add `cryptography`
for maintained Ed25519 primitives (a justified new dependency), not custom
crypto. Verify zstd is present in every packaged runtime. No Redis, task broker,
new database service or cloud SDK. One worker process owns its mutable SQLite
DB; one AniBridge process owns consumer updates and job scheduling per data
volume. Multiple ASGI workers sharing that volume are rejected at startup
using an exclusive OS lock; threads/read connections remain concurrent.

| Store | Owner | Purpose |
| --- | --- | --- |
| Worker DB | collector/publisher | durable identities/discovery, due work, mappings, revisions |
| Public directory | publisher writes immutable files | allowlisted provider artifacts and signed manifests only |
| Local catalog directory | consumer update manager | active, previous and staged immutable files |
| `anibridge_jobs.db` | AniBridge | released state plus additive catalog/trust/override/job state |

Never export a private DB using backup/VACUUM and call that sanitization.
Build a fresh allowlisted DB. Public snapshots are one per provider.

Implementation refinement approved 2026-09-27: the private snapshot runtime
may run in Linux containers while native resource enforcement remains gated.
Frozen Linux executables are gated too: the current child launcher requires a
Python interpreter supporting `-m`, which a onefile application does not provide.
Native package builds do not establish the 256-MiB child limit; macOS rejected
RLIMIT_AS in the first experiment. See 10-implementation-evidence.md.

## HTTP distribution and signed envelope

Worker serves a read-only directory itself; an external static server may
serve the same bytes. No public mutation, query, health-detail or telemetry API.
Routes relative to the explicitly configured source root:

```text
/catalog/v1/providers/{provider}/current.json
/catalog/v1/providers/{provider}/manifests/{revision}.json
/catalog/v1/providers/{provider}/artifacts/{sha256}.sqlite.zst
```

The root configuration ends before `/catalog`. `current.json` is exactly
`{"protocol_version":1,"revision":42}`; the client constructs the manifest path,
not a server-supplied URL. It is an unsigned cache hint, never a trust statement.
Manifest envelope is `{"payload":"<standard padded base64>","signatures":[
{"key_id":"<sha256 of raw public key>","sig":"<standard padded base64>"}]}`.
One to four unique signatures; Ed25519 signature length 64, raw public key 32
bytes. Signature covers the exact decoded payload bytes, before JSON parsing.
At least one configured, nonrevoked key must verify. Integer fields reject
booleans and must fit signed 64-bit; timestamp values are nonnegative. Reject duplicate JSON
keys, invalid UTF-8, NaN, noninteger numbers and unknown fields at every level.
Limits: pointer 4 KiB, envelope 64 KiB, decoded payload 32 KiB, nesting depth 8.

Required payload fields (all times integer Unix UTC seconds):

| Field | Type/constraint |
| --- | --- |
| protocol_version, identity_version | integer 1 |
| catalog_schema_version | integer 1 or 2; exact corresponding DDL from 09 |
| source_id | configured stable ASCII identifier, 1–64 `[a-z0-9._-]` characters |
| provider | aniworld.to, s.to or megakino |
| revision | positive signed-64-bit integer, monotonically increasing per source/provider |
| published_at, expires_at | publication time; expiry exactly published_at + 172800 (48 hours) |
| listing_checked_at | last complete accepted provider listing time |
| oldest_active_check_at | oldest successful detail check among active titles, null if incomplete |
| collection_state | healthy, partial, blocked, transport_error, parser_error, publishing_error or clock_error; no error text |
| coverage | object: titles = complete; details = partial or complete; mappings = partial or complete |
| counts | object with nonnegative counts for title, alias, entity, release, canonical_title, canonical_episode, identity_alias |
| artifact | object: sha256, sqlite_sha256 (64 lowercase hex), size_bytes, uncompressed_size_bytes (positive integers) |

Artifact path is derived from SHA-256; media format is fixed SQLite/zstd v1,
not negotiated by MIME. Header MIME may be application/octet-stream.
Catalog metadata and all counts must match the payload. No revision/build time
inside the DB: renewing signed metadata can reuse identical artifact bytes.
Per-row observations must be <= published_at + 300; first_seen <= observed.
coverage.details=complete means every current title has complete successful
details. coverage.mappings=complete means every current entity has a validated
map; unknown/split entities make mappings partial. Neither certifies playback
or rights. A failed refresh retains data but sets detail coverage partial.
No `observed_through` field: a single maximum timestamp hid stale rows.

## Trust, expiry and compatible readers

Pin source_id, root URL and public keys separately in local configuration.
No trust-on-first-use or verify=false. Official roots require HTTPS; explicitly
configured LAN HTTP is allowed for private self-hosting and remains signed.
Reject credentials/query/fragment in root URLs. Same origin and root path
only, no redirects to a different scheme even for an explicit HTTP source, maximum two redirects, validate each hop/DNS before connecting; private
addresses are allowed only for that explicitly configured source, with
allow_lan_http=true in its config (this grants LAN addressing as well as HTTP). Preserve
TLS hostname/certificate verification when pinning validated IPs. Provider
paths use the independent provider policy, never the catalog server origin.

Activation requires `published_at <= now+300`, `expires_at >= now-300` and
published_at not earlier than the last accepted publication time minus 300.
Persist last trusted wall-clock observation; a local clock moving backwards
more than 300 seconds suspends updates with clock_error. Monotonic clocks
bound operations. Repair system time; never accept HTTP Date as trusted time.
Expiry stops accepting a candidate, not searching an already verified catalog.
Expose stale_metadata and collection age separately. A repeated pointer/304
cannot extend expiry. Refetch unconditionally by expiry, with bounded retries.

Reserve a new revision transactionally before signing, never reuse it after a
crash. Persist highest **accepted** revision and payload digest per
(source_id,provider), independent of active revision. Lower rejects; equal
accepts only identical payload digest (redownload/recovery), higher proceeds
only through all artifact checks. Invalid or unsupported metadata never raises
the accepted floor. No auto-downgrade. Operator rollback selects only a locally
previously accepted compatible artifact and keeps the high-water mark. Persist
a rollback hold at that floor: polls must not reactivate the rejected revision;
a strictly higher accepted revision clears the hold. Recovery to previous after
corruption sets the same hold. Status exposes hold_revision (nullable).

Every 24 hours publish a new signed manifest, even for unchanged bytes; retain
original collection timestamps, collection_state and degraded coverage. This renews distribution
authenticity, not provider freshness. Retention is two distinct snapshots per
provider in total, including across schema transitions; it does not reserve an
additional compatible stream. Current readers recognize exact schemas1 and2.
An older reader presented with an unsupported schema retains its local last-good
and reports unsupported_schema; it needs a software/config update. A90-day
parallel-schema public hosting promise is withdrawn from this private policy;
any future public transition must be reviewed against the same disk budget.
Key overlap alone does not require keeping all intermediate catalog artifacts.

Routine key rotation uses a release/config update containing both keys first,
then dual signatures for at least 90 days, then an explicit release/config
revocation of the old key. No remotely self-authorized key delegation protocol.
Offline clients may need a software/config update; retain last-good meanwhile.
Compromise/lost key: stop publication, distribute a replacement/revocation
through the application release channel or explicit local config, verify its
fingerprint out of band, and resume with a higher revision. On restart do not serve artifacts whose only
trusted signature uses a now-revoked key; try a still-trusted previous version,
otherwise report not_ready. A malicious huge
revision may require an explicit new source_id/trust namespace; never clear
floors automatically. Signing secret is a read-only mounted secret outside
served paths, image, logs and state backups shared publicly.

Source URL/key/source_id changes are explicit local config changes, restart
required. Stage new-source catalogs independently; keep prior source active
until each replacement verifies, report switching and both provenances.
Retain old floors and one rollback artifact; no implicit reuse of keys or
merge of conflicting aliases. A return to an old source uses its old floor.
Operator rollback is an authenticated local operation (08), never an unsigned
remote instruction. Fresh clients cannot detect pre-installation replay within
the 48-hour validity window; document that limitation rather than claim TUF.

## Atomic activation and recovery

1. Serialize updates globally (one download/decompress/validate at a time).
   Verify manifest and bounds, reserve disk, stream to a unique temp file.
   Hash compressed bytes; bounded zstd decompress to another temp file,
   hash SQLite bytes and enforce exact signed sizes and both local caps.
   Decompression runs under a 60s wall/256-MiB child budget with <=64-MiB
   decoder window, one zstd frame, no trailing bytes or external dictionary.
   Publisher uses that same frame/window contract. Kill/reap within 2s.
2. Validate in a bounded subprocess, read-only, extensions disabled,
   `trusted_schema=OFF`, `query_only=ON`; inspect schema before querying data.
   Run integrity, FK, semantic/identity checks and fixed query fixtures within
   a 256-MiB child budget. Reject resource exhaustion, do not retry unbounded.
3. Close DB, fsync candidate, rename on the same filesystem to its
   content-addressed final filename, fsync directory. Do not overwrite an
   existing immutable file; verify/reuse identical bytes.
4. Under the catalog read-acquisition mutex, one private-DB transaction with
   `synchronous=FULL` stores accepted revision/payload digest, manifest,
   artifact filename/digest, previous filename, active source/provider row,
   activation generation, timestamps and status. Commit is the sole switch.
   There is no second active-pointer file. Swap the in-process handle registry
   before releasing the mutex; on failure stop acquisitions and rebuild it
   from the committed DB. A DB commit failure leaves the old pointer intact.
5. Readers capture the selected provider handles and leases under that same
   mutex for the entire response. Existing readers finish against old files;
   new readers see the committed set. Open with mode=ro, immutable=1; never
   mutate files in place. Cross-provider publications need not be simultaneous.
6. Cleanup takes the mutex, excludes active/previous/staged/leased files and
   removes only unreferenced files. No file used by a reader is deleted, even
   on platforms where unlink would technically work.

On restart validate saved manifest/digest and file before serving it (expiry
alone does not invalidate it). For a committed, previously fully validated
version admitted by the current validator, re-verify the signature, stored digest,
exact byte length and whole-file SHA-256; identical authenticated bytes preserve
that semantic validation. Persist a private validator-version receipt at admission,
bound to source ID, configured origin and the exact pinned key set (key ordering
is immaterial). Changing any of those invalidates fast receipt reuse.

For a new signed revision referencing the identical artifact, first verify the
new manifest/source/pins/revision/expiry/schema and configured caps. If the
active same-source receipt uses the current validator and trust context, its
previous signed row contract (provider/schema/identity/header/counts/coverage
and complete artifact metadata) matches, and publication time does not regress,
hash the retained regular nonsymlink file in a bounded child. Reuse these
validated bytes without downloading, decompressing or rescanning semantic rows.
Commit the new receipt, manifest, active revision and trust floor atomically;
keep the previous distinct artifact. Unchanged polls still verify manifest and
local digest. A changed source/origin/pins or row contract requires full admission;
missing local bytes fall through to full admission, corrupt bytes reject safely.
A signature/expiry/schema failure cannot advance the floor. This survives restart
only through the durable receipt, never an in-memory digest shortcut.

After a validator correction, older receipts require full bounded validation once
before fast recovery is permitted; a rejected prior receipt cannot advance or
erase the trust floor. The receipt is private metadata, not a new wire identity.
New or uncommitted artifacts still require all admission checks. A precommit final file is an orphan, a postcommit
file is authoritative. Remove orphan temps only after acquiring the process
lock and consulting DB references. If active bytes are missing/corrupt, select
validated local previous bytes transactionally, preserve the revision floor,
and report recovered_previous; otherwise not_ready. Restore the private DB
and catalog volume together; a backup rollback cannot resist replay to its
lost high-water mark. Document this backup boundary.

Consumer defaults: compressed artifact <=256 MiB, SQLite <=1 GiB/provider,
managed catalog directory <=8 GiB total; active + one previous/provider plus
one staged update. Reserve compressed+uncompressed bytes +512 MiB free before
fetch; recheck during writes, stop safely on ENOSPC. Evict only unreferenced
versions, never active/previous or jobs. If protected files consume the budget,
reject update as storage_full. Compressed downloads are removed after install.
Full semantic validation uses a private 32-MiB SQLite page cache; search
connections retain their 8-MiB cache. This is within the existing 256-MiB
child envelope, not a larger memory limit or weaker admission.
Download wall deadline 10 minutes; validation 120 seconds +2 seconds kill/reap;
connect 5 seconds, read inactivity 15 seconds, pool 1 second. Failure keeps
last-good; retry after 5, 15, 60 minutes, then normal polling. Configurable byte
limits are in 04; timeouts are fixed v1 constants. Raising limits requires
capacity measurements, not disabling validation.

Publisher fsyncs artifact, manifest and directories before atomically replacing
current pointer (or completes object uploads before replacing the pointer).
Retain the current and one previous **distinct artifact per provider**, and the
current manifest plus the latest manifest referencing that previous artifact.
Renewals reuse bytes and do not accumulate manifests. This replaces the former
72-hour full-snapshot grace; historical failures stay recorded in11. Transfer
leases protect files across processes, with directory-open/unlink serialization
and serving from the leased descriptor. At most16 static responses,15s socket
inactivity and600s streaming deadline bound transfer extensions. Cleanup after
publication and before subsequent builds deletes unleased obsolete owned files.
Prune publication rows to those references; retain the separate burned revision
floor and compact identity/discovery/mapping/checkpoint records. Never retain
full catalog copies for every intermediate publication.

current.json uses exact-byte ETag and Cache-Control:no-cache,must-revalidate.
Immutable successful manifests/artifacts use public,max-age=31536000,immutable;
missing/error responses use no-store (no negative cache). An external server
must preserve the same policies **and shared transfer lease/cleanup exclusion**;
serving static files without an equivalent opened-file guard is unsupported.

If a derived manifest/artifact returns404 or410, the consumer invalidates the
cached current pointer, re-fetches it unconditionally with request no-cache, and
retries once through normal signature/schema/revision/size admission. Two
attempts share a900s operation deadline; each fetch retains existing deadlines
and byte/origin/DNS/TLS restrictions. A second miss, expiry, unsupported schema,
invalid signature or other failure leaves local last-good and trust floor intact;
normal5/15/60m update backoff applies afterward. Active installed jobs do not
need an old remote snapshot. No replay floor is weakened to recover a miss.

Worker total budget is30,000,000,000 bytes: default20,000,000,000 state,
9,000,000,000 output, and1,000,000,000 reserved for image/config/key and bounded
runtime logs. Count SQLite/WAL/SHM, checkpoints, backups, logs, artifacts and
staging together; require free-space and incremental construction headroom.
Protected transfers or verified backups can stop publication/admission as
storage_full, never cause last-good data deletion. The oversized profile is
removed; old explicit profiles/overcommitted quotas require a configuration
update, with existing data untouched. See03 for measured workload limits.

Private artifact compatibility refinement (2026-09-30): protocol/identity v1
readers in this implementation recognize exact catalog schemas1 and2. Schema2
uses the compact layout in09; signed schema version, database header and catalog
row must agree. New worker publications use2, prior pilot snapshots remain
readable, and older readers retain their last-good1 on an unsupported2 update.
No mainline private-state rewrite, public default or public overlap readiness
is implied. Resource/byte caps remain unchanged.
