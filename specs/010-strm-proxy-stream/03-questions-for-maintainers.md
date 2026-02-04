# Questions For Maintainers

## Status

Draft

## Scope

Enumerate unresolved questions that block final design decisions, each with why it matters and what decision it affects.

## Last updated

2026-02-03

## Product And User Workflow

- Q: Which media server(s) are in scope (Jellyfin, Emby, Kodi, Plex)? Why it matters: each client has different STRM and Range behaviors. Decision impacted: endpoint contracts, Range policy, playlist handling, and test matrix.
- Q: Is STRM proxy mode expected to be the default or opt-in via `STRM_PROXY_MODE`? Why it matters: default changes affect existing users. Decision impacted: rollout plan, backward compatibility, and documentation.
- Q: Should STRM proxy mode apply to all sites (AniWorld, s.to, megakino) or only a subset? Why it matters: resolver capabilities differ by site. Decision impacted: routing logic and query param validation.
- Q: Should proxy URLs be stable across provider changes, or should `provider` be required in the STRM URL? Why it matters: stateless identity vs deterministic provider selection. Decision impacted: URL contract and cache key shape.
- Q: Is a UI/CLI refresh action planned soon or only as a later phase? Why it matters: influences persistence priority. Decision impacted: whether to include mapping table scaffolding in early iterations.

## Deployment And Ingress

- Q: What reverse proxies are used in real deployments (Traefik, Nginx, Caddy, none)? Why it matters: buffering and timeout defaults affect streaming. Decision impacted: required documentation and configuration guidance. [Traefik Buffering Middleware](https://doc.traefik.io/traefik/middlewares/http/buffering/), [Nginx proxy_buffering](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering)
- Q: Are there multi-worker or multi-replica deployments (uvicorn workers, multiple containers)? Why it matters: in-memory cache consistency and signing validation. Decision impacted: cache design and token scheme.
- Q: Is AniBridge typically exposed only on LAN or over WAN? Why it matters: security and auth requirements differ. Decision impacted: default auth mode and signing strictness.
- Q: Are deployments typically behind Gluetun or full VPN, or is `PROXY_*` the main method? Why it matters: upstream token binding and retry strategy. Decision impacted: resolver retry policy and proxy configuration assumptions. See `docs/src/guide/quickstart.md:62` and `docs/src/guide/networking.md:8`.

## Security And Access Control

- Q: Must the proxy be accessible without auth on trusted LANs, or should auth always be required? Why it matters: open proxy risk. Decision impacted: default `STRM_PROXY_AUTH` setting.
- Q: If using HMAC signing, what expiry window is acceptable (seconds vs minutes)? Why it matters: token leakage risk vs playback stability. Decision impacted: signing scheme and clock skew tolerance. [RFC 2104](https://www.rfc-editor.org/rfc/rfc2104)
- Q: Should we support per-client allowlists (CIDR or IP ranges)? Why it matters: reduces open proxy abuse. Decision impacted: auth design and config surface.
- Q: Is SSRF protection required (block private IPs, metadata IPs, or non-HTTP schemes)? Why it matters: proxy endpoints can be abused to access internal resources. Decision impacted: URL validation and allowlist/denylist logic. [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)

## HLS Behavior

- Q: Do we have examples of actual provider HLS playlists used in STRM (master vs media, encrypted vs clear)? Why it matters: rewrite rules and tag coverage depend on real-world inputs. Decision impacted: rewrite parser and test vectors. [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)
- Q: Are EXT-X-KEY URIs routinely used by the providers? Why it matters: key proxying and redaction requirements. Decision impacted: key handling policy and logging.
- Q: Are playlists using relative URIs, absolute URIs, or both? Why it matters: rewrite must resolve relative URIs correctly. Decision impacted: base URL resolution rules. [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)
- Q: Are audio/subtitle renditions required (`EXT-X-MEDIA`)? Why it matters: incomplete rewrites break playback. Decision impacted: tag coverage and tests. [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)
- Q: Are byte-range segments (`EXT-X-BYTERANGE`) used by providers? Why it matters: range proxying for segment files may be necessary. Decision impacted: range handling on segment requests.

## Range And Streaming Behavior

- Q: Do clients send `HEAD` requests before playback, and should those be supported? Why it matters: some players probe metadata via HEAD. Decision impacted: HEAD passthrough implementation.
- Q: What chunk sizes are safe for segment proxying (e.g., 64KB, 256KB)? Why it matters: affects memory and throughput. Decision impacted: streaming implementation and performance tuning.
- Q: Do deployments require HTTP/2 or HTTP/3, or is HTTP/1.1 sufficient? Why it matters: Range and streaming semantics are defined but proxy behavior differs by protocol. Decision impacted: server configuration guidance. [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110)

## Resolver Integration

- Q: Does the aniworld resolver expose required headers (Referer, User-Agent, cookies) for direct URLs? Why it matters: proxy requests may require those headers. Decision impacted: header capture and caching design.
- Q: Should the proxy attempt provider fallback on refresh (switch providers) or only re-resolve the same provider? Why it matters: could change quality/availability. Decision impacted: refresh policy.
- Q: Is resolver latency acceptable for on-demand playback, or must cached URLs be used? Why it matters: playback startup time. Decision impacted: cache TTL and prefetching.

## Caching And Persistence

- Q: Is in-memory caching sufficient for MVP, or do we need persistence sooner? Why it matters: multi-worker restarts can invalidate cache. Decision impacted: whether to introduce StrmUrlMapping early. See `specs/004-strm-file-support/refresh-boilerplate.md:32`.
- Q: If persistence is added, should storage be in SQLite only or also optional external DB? Why it matters: migration complexity. Decision impacted: data layer abstraction.
- Q: Should we cache playlist rewrites, resolved URLs, or both? Why it matters: cache hit rate vs correctness. Decision impacted: cache data model.
- Q: What TTL is acceptable before refresh for typical providers (minutes vs hours)? Why it matters: token expiration and resolver load. Decision impacted: cache policy.

## Observability And Supportability

- Q: What logging level is acceptable for production (info vs debug)? Why it matters: sensitive data exposure vs troubleshooting. Decision impacted: log redaction and default logging scope.
- Q: Is Prometheus metrics output desired, or is log-only observability sufficient? Why it matters: operational insight. Decision impacted: metrics instrumentation.
- Q: Should we emit structured logs (JSON) for proxy requests? Why it matters: easier correlation. Decision impacted: logging format.

## Backward Compatibility And Migration

- Q: How should existing `.strm` files be handled when proxy mode is enabled? Why it matters: users may already have libraries indexed. Decision impacted: migration/regen strategy.
- Q: Should we provide a tool to bulk-rewrite existing `.strm` files, or rely on re-import? Why it matters: user effort. Decision impacted: tooling scope.

## Legal / Compliance / Policy

- Q: Are there any provider terms or policies that constrain proxying behavior or URL retention? Why it matters: legal exposure. Decision impacted: logging retention, caching, and persistence policies.
- Q: Should the proxy enforce geographic restrictions (e.g., deny access from outside a region)? Why it matters: compliance and account risk. Decision impacted: auth and policy logic.
