# Questions For Maintainers

## Status

Answered

## Scope

Enumerate unresolved questions that block final design decisions, each with why it matters and what decision it affects.

## Last updated

2026-02-03

## Product And User Workflow

- Q: Which media server(s) are in scope (Jellyfin, Emby, Kodi, Plex)? Why it matters: each client has different STRM and Range behaviors. Decision impacted: endpoint contracts, Range policy, playlist handling, and test matrix.
- A: Initial focus is on Jellyfin due to popularity and STRM support; Emby, Kodi ^and Plex may be considered later.
- Q: Is STRM proxy mode expected to be the default or opt-in via `STRM_PROXY_MODE`? Why it matters: default changes affect existing users. Decision impacted: rollout plan, backward compatibility, and documentation.
- A: STRM proxy mode should be enabled by default in future releases once stable, with opt-out for direct mode. No backward compatibility focus is needed.
- Q: Should STRM proxy mode apply to all sites (AniWorld, s.to, megakino) or only a subset? Why it matters: resolver capabilities differ by site. Decision impacted: routing logic and query param validation.
- A: Initially apply STRM proxy mode to all supported sites for consistency; more providers should be added easily over time.
- Q: Should proxy URLs be stable across provider changes, or should `provider` be required in the STRM URL? Why it matters: stateless identity vs deterministic provider selection. Decision impacted: URL contract and cache key shape.
- A: I do not have a strong preference; either approach is acceptable as long as the used URL format is stable and always resolves to the correct content regardless of provider changes.
- Q: Is a UI/CLI refresh action planned soon or only as a later phase? Why it matters: influences persistence priority. Decision impacted: whether to include mapping table scaffolding in early iterations.
- I do have the opinion that persistence in for instance the sqlite db should be added. This would allow for easier future expansion of the feature, and also allow for better caching strategies to be implemented in the future.

## Deployment And Ingress

- Q: What reverse proxies are used in real deployments (Traefik, Nginx, Caddy, none)? Why it matters: buffering and timeout defaults affect streaming. Decision impacted: required documentation and configuration guidance. [Traefik Buffering Middleware](https://doc.traefik.io/traefik/middlewares/http/buffering/), [Nginx proxy_buffering](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering)
- A: Traefik and Nginx are the most common, maybe Caddy as well.
- Q: Are there multi-worker or multi-replica deployments (uvicorn workers, multiple containers)? Why it matters: in-memory cache consistency and signing validation. Decision impacted: cache design and token scheme.
- A: I do not have specific data on this.
- Q: Is AniBridge typically exposed only on LAN or over WAN? Why it matters: security and auth requirements differ. Decision impacted: default auth mode and signing strictness.
- A: Both LAN and WAN deployments are possible; but LAN deployments are more common as the documentation encourages that. In the future a WebUI may be added which would increase WAN deployments, but the WebUI would likely have its own auth separate from the STRM proxy auth and not communicate with AniBridge via WAN and STRM Proxy Urls.
- Q: Are deployments typically behind Gluetun or full VPN, or is `PROXY_*` the main method? Why it matters: upstream token binding and retry strategy. Decision impacted: resolver retry policy and proxy configuration assumptions. See `docs/src/guide/quickstart.md:62` and `docs/src/guide/networking.md:8`.
- A: Only glutun or full VPN deployments are common, the in app proxy will be deprecated in the near future. DO NOT use the in app proxy for STRM proxying.

## Security And Access Control

- Q: Must the proxy be accessible without auth on trusted LANs, or should auth always be required? Why it matters: open proxy risk. Decision impacted: default `STRM_PROXY_AUTH` setting.
- A: I do not have a strong preference, but auth should always be required for WAN deployments.
- Q: If using HMAC signing, what expiry window is acceptable (seconds vs minutes)? Why it matters: token leakage risk vs playback stability. Decision impacted: signing scheme and clock skew tolerance. [RFC 2104](https://www.rfc-editor.org/rfc/rfc2104)
- A: I do not know RFC 2104 well enough to answer this.
- Q: Should we support per-client allowlists (CIDR or IP ranges)? Why it matters: reduces open proxy abuse. Decision impacted: auth design and config surface.
- A: I do not have a strong preference; a working implementation is the current priority, security can be improved later.
- Q: Is SSRF protection required (block private IPs, metadata IPs, or non-HTTP schemes)? Why it matters: proxy endpoints can be abused to access internal resources. Decision impacted: URL validation and allowlist/denylist logic. [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- A: I do not know SSRF well enough to answer this. A working implementation is the current priority, security can be improved later.

## HLS Behavior

- Q: Do we have examples of actual provider HLS playlists used in STRM (master vs media, encrypted vs clear)? Why it matters: rewrite rules and tag coverage depend on real-world inputs. Decision impacted: rewrite parser and test vectors. [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)
- A: I assume both master and media playlists are used. For further details look at the examples under specs/010-strm-proxy-stream/Examples which include a url to the m3u8 playlist (current strm file) and the downloaded raw m3u8 file.
- Q: Are EXT-X-KEY URIs routinely used by the providers? Why it matters: key proxying and redaction requirements. Decision impacted: key handling policy and logging.
- A: I do not know for further details look at the examples under specs/010-strm-proxy-stream/Examples which include a url to the m3u8 playlist (current strm file) and the downloaded raw m3u8 file.
- Q: Are playlists using relative URIs, absolute URIs, or both? Why it matters: rewrite must resolve relative URIs correctly. Decision impacted: base URL resolution rules. [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)
- A: I do not know for further details look at the examples under specs/010-strm-proxy-stream/Examples which include a url to the m3u8 playlist (current strm file) and the downloaded raw m3u8 file.
- Q: Are audio/subtitle renditions required (`EXT-X-MEDIA`)? Why it matters: incomplete rewrites break playback. Decision impacted: tag coverage and tests. [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)
- A: I do not know for further details look at the examples under specs/010-strm-proxy-stream/Examples which include a url to the m3u8 playlist (current strm file) and the downloaded raw m3u8 file.
- Q: Are byte-range segments (`EXT-X-BYTERANGE`) used by providers? Why it matters: range proxying for segment files may be necessary. Decision impacted: range handling on segment requests.
- A: I do not know for further details look at the examples under specs/010-strm-proxy-stream/Examples which include a url to the m3u8 playlist (current strm file) and the downloaded raw m3u8 file.

## Range And Streaming Behavior

- Q: Do clients send `HEAD` requests before playback, and should those be supported? Why it matters: some players probe metadata via HEAD. Decision impacted: HEAD passthrough implementation.
- A: I do not know, a working implementation is the current priority.
- Q: What chunk sizes are safe for segment proxying (e.g., 64KB, 256KB)? Why it matters: affects memory and throughput. Decision impacted: streaming implementation and performance tuning.
- A: I do not know, a working implementation is the current priority.
- Q: Do deployments require HTTP/2 or HTTP/3, or is HTTP/1.1 sufficient? Why it matters: Range and streaming semantics are defined but proxy behavior differs by protocol. Decision impacted: server configuration guidance. [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110)
- A: I do not know RFC 9110, a working implementation is the current priority.

## Resolver Integration

- Q: Does the aniworld resolver expose required headers (Referer, User-Agent, cookies) for direct URLs? Why it matters: proxy requests may require those headers. Decision impacted: header capture and caching design.
- A: I do not know for sure, could be, worth checking.
- Q: Should the proxy attempt provider fallback on refresh (switch providers) or only re-resolve the same provider? Why it matters: could change quality/availability. Decision impacted: refresh policy.
- A: I do not have a strong preference; either approach is acceptable as long as the used URL format is stable and always resolves to the correct content regardless of provider changes, but probably re-resolving the same provider is simpler.
- Q: Is resolver latency acceptable for on-demand playback, or must cached URLs be used? Why it matters: playback startup time. Decision impacted: cache TTL and prefetching.
- A: I do not have specific data on this, but caching is generally preferred to reduce latency.

## Caching And Persistence

- Q: Is in-memory caching sufficient for MVP, or do we need persistence sooner? Why it matters: multi-worker restarts can invalidate cache. Decision impacted: whether to introduce StrmUrlMapping early. See `specs/004-strm-file-support/refresh-boilerplate.md:32`.
- A: I would appreciate if persistence in for instance the sqlite db would be added sooner rather than later, as it would allow for easier future expansion of the feature, and also allow for better caching strategies to be implemented in the future.
- Q: If persistence is added, should storage be in SQLite only or also optional external DB? Why it matters: migration complexity. Decision impacted: data layer abstraction.
- A: Only SQLite is needed for now, external DB support can be considered later if necessary.
- Q: Should we cache playlist rewrites, resolved URLs, or both? Why it matters: cache hit rate vs correctness. Decision impacted: cache data model.
- A: I do not have a strong preference; either approach is acceptable as long as the approach is stable and allows for correct content delivery.
- Q: What TTL is acceptable before refresh for typical providers (minutes vs hours)? Why it matters: token expiration and resolver load. Decision impacted: cache policy.
- A: I do not have specific data on this, but a balance between token expiration and resolver load is generally preferred.

## Observability And Supportability

- Q: What logging level is acceptable for production (info vs debug)? Why it matters: sensitive data exposure vs troubleshooting. Decision impacted: log redaction and default logging scope.
- A: Info level logging is acceptable for production, with sensitive data redacted. Debug level can be used for troubleshooting when necessary. If necessary create trace level logging for highly sensitive data.
- Q: Is Prometheus metrics output desired, or is log-only observability sufficient? Why it matters: operational insight. Decision impacted: metrics instrumentation.
- A: Prometheus metrics output is not our priority!
- Q: Should we emit structured logs (JSON) for proxy requests? Why it matters: easier correlation. Decision impacted: logging format.
- A: I am unsure about this, as our current logging follows the structure yyyy-mm-dd hh:mm:ss | LEVEL    | path-to-file(example app.db.models):function:line - log line

## Backward Compatibility And Migration

- Q: How should existing `.strm` files be handled when proxy mode is enabled? Why it matters: users may already have libraries indexed. Decision impacted: migration/regen strategy.
- A: IGNORE. We completely ignore existing .strm files and backward compatibility.
- Q: Should we provide a tool to bulk-rewrite existing `.strm` files, or rely on re-import? Why it matters: user effort. Decision impacted: tooling scope.
- A: NOT NEEDED.

## Legal / Compliance / Policy

- Q: Are there any provider terms or policies that constrain proxying behavior or URL retention? Why it matters: legal exposure. Decision impacted: logging retention, caching, and persistence policies.
- A: Not known, current priority is a working implementation.
- Q: Should the proxy enforce geographic restrictions (e.g., deny access from outside a region)? Why it matters: compliance and account risk. Decision impacted: auth and policy logic.
- A: NO.
