# Public catalog service contract

Status: decided product direction, not implemented or deployed. This is the
target boundary for the normal public product; ordered acceptance gates live in
[ISSUES.md](ISSUES.md). No pilot host, preview image, compose overlay or moving
tag is this service.

## Product surface

A normal AniBridge install gets catalog search from one official, anonymous,
read-only metadata service. A fresh install needs no signup, account, API key,
endpoint URL, source ID or token file.

- Public surface is exactly one read query, `POST /catalog/v1/query`, on the
  official HTTPS host, returning the existing finite wire model (protocol v1).
- Anonymous: no bearer, cookie or account. Abuse control is admission policy,
  not a credential.
- Read-only: published catalog rows only. No collection, job creation, grabs,
  media, management, qBittorrent or STRM routes.
- The service answers from local immutable catalogs. It never fetches a
  client-named source, upstream origin or player URL, and request models forbid
  unknown fields.
- The worker keeps its private bearer credential and private backend bind. Only the
  public edge is anonymous; the edge holds the backend credential. That
  credential never ships in distributed clients/images, responses or logs.
- Self-hosting, private catalogs and explicit origin/token configuration remain
  supported advanced options. They are not required and not the default.

## Protections that stay

The public edge is additive. Do not remove or weaken existing boundaries:
backend bearer on the worker, loopback default bind, `MANAGEMENT_API_TOKEN`,
optional qBittorrent session auth on `/api/v2`, STRM output/route protections,
local media/job resource admission, origin validation and the private-HTTP
opt-in, redirect/DNS/TLS checks, or bounded request/response limits. The public
service must not reuse the worker as an all-router API, and no shared private
bearer may ship in client images, sample env files or documentation examples.

## Identity and admission (target)

Current admission is a global token bucket (200/s, burst 256, eight active),
per-operation caps (titles 2, native 4, recent 4), and one per-socket-address
bucket (100/s, burst 128, four active, 64 addresses). Identity is
`http.client.host`. When requests share a proxy socket address, they share one
bucket. Anonymous IP-based admission also groups clients behind the same NAT;
it cannot promise a separate allowance for each person.

Target model:

- Enforce identity-based admission at the trusted public ingress. If identity
  is forwarded to an application, accept it only from configured trusted proxy
  peers; otherwise the socket address is authoritative. A client-supplied
  forwarded header must not grant a fresh allowance. Existing ingress features
  may implement this; a new gateway service is not required by this contract.
- Three independent budgets, sized and measured separately:
  - request rate and burst per identity (fairness),
  - work allowance per identity (derive weights from measured operation/page
    cost; multi-page fan-out must not bypass the allowance),
  - concurrent queries and resource slots (memory, SQLite, connection pool),
    which protect the process regardless of request rate. Local download/child
    budgets are separate from the hosted metadata read path.
- Global caps remain the origin protection and may reject even a well-behaved
  identity. Rejections are explicit (`429`/`503` with `Retry-After`), never
  truncated or silently empty results.

## Caching and failure

The client already has a per-install cache (60 s TTL, 24 h stale allowance,
3 s deadline, single-flight per request digest, at most eight in-flight and 64
waiters, eight connections). A public service cannot rely on per-install state:
measure shared caching and single-flight against the admitted workload. If
used, their keys must include validated request, source/provider and catalog
revision. A separate distributed-cache deployment is not a prerequisite by itself.

- Cache hits must still match the current revision floor; stale serving is only
  for eligible transport/timeout/429/503 cases, never cold cache, auth failure
  or contract violation, and must be labelled as stale.
- Keep the current single-attempt client unless measured recovery warrants
  retries. Any added retries need a bounded, jittered budget; authentication,
  validation and contract failures are not retryable. A documented 429 backoff
  must honor `Retry-After` without amplifying a failed query across users.
- An outage must degrade to explicit `503` (or labelled stale) with truthful
  partial-provider headers, not a successful empty catalog.
- The public route is `POST`, which a conventional CDN will not cache. The shared
  cache would need explicit application/proxy support (or a versioned cacheable
  GET form, decided separately); CDN availability alone proves nothing.

## Compatibility

Clients and the public edge evolve independently, so the read contract needs an
explicit compatibility policy. The `/catalog/v1/query` route already versions
the request surface and `Response.version` is 1. Unknown request shapes fail
validation; adding a redundant body version is not required.

- The official endpoint must reject unsupported request versions and unknown
  operations with an actionable client error, and the client must reject an
  unsupported response version instead of treating it as empty.
- Decide and document the supported client-version window and a deprecation
  path before removing fields.
- Provider-specific unavailability is explicit; absence in one failed provider
  cannot become a successful empty result.
- Response rows keep identity/magnet compatibility rules from
  [identity.md](identity.md); public availability does not change local
  admission, corrections or frozen job identities.

## Privacy and retention

Anonymous does not mean unobserved. The read path must not log titles, queries,
raw IPs, user agents or credentials; diagnostics stay bounded (reason,
operation, duration, provider, aggregate counters). Any identity key used for
admission is ephemeral, bounded and not correlated into long-lived profiles.
TLS-only ingress, no cookies on the read route, documented access-log and
retention policy, and an explicit legal/rights decision are prerequisites for
public traffic. Disabled application access logs are not an end-to-end privacy
guarantee; proxies and the hosting operator still see requests.

## Providers and freshness

The wire model accepts `aniworld.to`, `s.to`, `megakino` and `filmo.to`, with
Filmo as the movie extension. The public service must declare its supported
provider and media-type set rather than inherit the union silently. Every
response already carries provider, revision, snapshot digest and
`listing_checked_at`; the service must not imply completeness or freshness
beyond measured publication state. Coverage, mapping accuracy and media
extraction claims remain subject to [ISSUES.md](ISSUES.md) and do not block a
declared, narrower public scope.

## Operations and release

Production is an operational setup plus client default/auth changes, not a flag
flip on the private pilot. The pilot uses a shared bearer and preview image
channel. Re-query its actual binds, source digest, ingress and serving state;
source defaults do not establish deployed configuration. Publishing preview
images or merging the draft does not create the public service.

- Staging and production have separate configuration, credentials and traffic.
  Promote the same tested immutable artifact into production; record each
  component's candidate and rollback digest before traffic moves.
- A canary receives a bounded traffic share first; revert on error/latency
  thresholds, not by editing a moving tag.
- Restore from the admitted backup set and last-good publication must be
  rehearsed; a successful image build is not capacity or restore proof.
- Capacity claims require measured concurrency, latency and resource headroom.
  Do not invent the production URL, traffic volume or performance numbers.

## Decisions still required

Official hostname and service owner; edge identity attestation mechanism;
per-identity rate/weight/concurrency values and fairness target; shared-cache
TTL/stale policy and whether a cacheable GET form is added; supported client
version window; declared provider set for v1; access-log/retention period and
legal approval; capacity targets; staging and production image identities;
release line and prerelease naming.
