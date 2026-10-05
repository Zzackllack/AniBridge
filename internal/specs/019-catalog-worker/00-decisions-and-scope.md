# Decisions and boundaries

## Product decisions accepted on 2026-09-26

1. The maintainer's hosted catalog is the default source when a public source
   is approved and available. The source is configurable. A future first-run
   WebUI can present a source choice; the worker cannot depend on that UI.
2. AniBridge downloads selected provider artifacts and performs search locally.
   Remote search and per-title shards require a separate architecture/privacy
   decision informed by measurements; do not implement three backends now.
   Normal Torznab searches, including broad season searches, must not probe
   every provider episode or video host. Resolve the chosen source locally
   after a grab; validate the grab/queue behavior with real *arr clients.
   Quality sampling runs asynchronously on the local instance, never blocking
   search. Until usable evidence exists, quality is unknown, not assumed 720p.
   See `08-decision-follow-up.md` for estimate scope and bounds, and
   `09-artifact-schema-and-identities.md` for the fixed v1 data contract.
   For an actual download or stream, that same local AniBridge instance fetches
   the configured provider page and resolves the chosen video host (including
   VOE). The worker does not serve or proxy user video requests.
3. Publish the minimum useful automation data: provider identity, titles and
   aliases, media type, relative paths, episode structure, languages, and
   permitted identifiers/mappings. Do not publish artwork, descriptions,
   browser state, direct media URLs, or tokens. Provider-advertised quality
   hints, if they exist, need provenance and separate validation; never present
   a guess as a measured episode quality or codec.
4. AniWorld is the first complete vertical slice. Intended public release
   includes AniWorld, Serienstream, and megakino. Each provider can publish
   and fail independently.
5. For actively releasing titles, aim to discover a new episode within about
   six hours under normal provider availability. Historical titles have a
   slower schedule. This is a service target to measure, not a hard claim.
6. Measure ordinary AniBridge under a 1 GiB RAM / 2 vCPU envelope. Existing
   installations start using their last good catalog without waiting for a
   network fetch. Fresh-install time and disk cost need benchmarks.
7. Package the worker as a portable Docker service. The maintainer may use an
   external server; no Oracle, home-network, GCP, or object-store SDK may be
   required for correctness. Worker resource use must remain bounded even if
   the maintainer has a 4-vCPU/24-GiB machine.
8. Keep the last compatible catalog on failed or stale updates. Default to
   catalog-only fallback; offer explicit, targeted local refresh as an option.
   Targeted results live in a separate local layer.
9. Do not send search terms or automatic title-demand telemetry to the hosted
   worker in the first release. A future opt-in request feature needs a
   separate privacy and abuse design.
10. The worker uses no browser or CAPTCHA solver. It must classify challenge
    pages and blocked responses, back off, retain previous good data, and
    report provider degradation. User-side video-host challenges remain an
    AniBridge concern.
11. Persistent local mapping corrections come first. Centrally reviewed
    corrections may be added later, with a moderation workflow.
12. Build the new architecture independently of PR #119. Reuse its verified
    behavior, parsers, mapping rules, and tests selectively, without importing
    its API-coupled indexer wholesale or requiring its migrations. No PR #119
    experimental database migration or compatibility layer is in scope.
13. The worker computes canonical title and episode mappings and persists
    them incrementally. Publish permitted compact mappings in snapshots;
    do not mirror upstream payloads. Size concerns require measurement before
    replacing local snapshots with remote search. A bounded canonical-ID
    fallback on an ID-bearing local miss may contact the configured canonical
    metadata source. Match against local entries; missing or ambiguous episode
    mappings stay unresolved. No hosted-worker query API is introduced.
14. Persist valid grabs before source resolution. Resolve when the job runs;
    retain challenge-blocked jobs for operator retry/future local browser
    assistance. Reject malformed or unauthorized grabs, not merely a
    currently unreachable provider. Paused jobs perform no source resolution.
15. Expose authenticated management HTTP endpoints on the local AniBridge
    instance for mapping corrections, refresh tasks, and job status/retry.
    A CLI is not the required operator interface. No WebUI/browser implementation
    or public hosted-worker mutation API is implied.
16. Include a real recent-release RSS feed with pagination and stable discovery
    timestamps. Snapshot rebuilds must not re-announce the entire back catalog.
17. The intended release is v3.0.0. Preserve supported mainline private data;
    document deliberate breaking changes. Experimental #119 schemas are
    unsupported and must not be silently stamped as a mainline schema.

## Explicit tradeoffs

- A central catalog reduces repeated catalog crawling, but its egress IP can
  become blocked. Last-good data, provider-specific status, and a portable
  self-hosted worker are part of the product, not optional decorations.
- Provider metadata and canonical metadata have distinct source and rights
  questions. Hosting an artifact outside GitHub does not answer either.
- A snapshot may be much larger on disk than in compressed transfer; it need
  not be loaded into Python memory. Size, temporary disk use, and download
  cadence must be measured before introducing shards or delta updates.
- SHA-256 content hashes can prevent unnecessary writes after a detail fetch.
  They do not tell us whether a provider page changed before fetching it.
  Scheduling and provider update signals reduce HTTP requests.
- The worker must support modest hardware by using lower concurrency and more
  time. The maintainer's larger machine is a speed profile, not a correctness
  requirement.

## Non-goals for the initial worker

- WebUI, Chromium, CAPTCHA solving, video-host extraction, direct download,
  qBittorrent emulation, and transcoding.
- Hosted query API, demand tracking, user accounts, central correction
  submissions, community contribution ingestion, and cross-instance sync.
- Redis/Celery/Postgres/Turso migration without a demonstrated need.
- Mirroring Skyhook/TVDB/TMDb payloads, artwork, or provider HTML.
- Automatic local full-provider reindexing inside every AniBridge instance.
- Public artifact redistribution before C7 clearance, or a hosted default
  before the separate C8 deployment gate in `05-validation-and-gates.md`.

## Meaning of complete

The private vertical slice demonstrates the entire producer → artifact →
consumer → Torznab query path with interruption recovery and measured limits.
The intended v3.0.0 functional release additionally covers all three providers,
distribution security, multi-architecture Docker images, and the relevant
Sonarr/Prowlarr/Radarr flows. Public data redistribution needs C7 clearance;
the hosted-default launch additionally needs C8 deployment approval. A green unit suite alone does not establish these.
