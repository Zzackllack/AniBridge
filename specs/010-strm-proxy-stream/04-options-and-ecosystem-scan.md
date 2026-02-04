# Options And Ecosystem Scan

## Status

Draft

## Scope

Survey existing libraries and proxy solutions relevant to HLS playlist rewriting, streaming proxy behavior, Range handling, and signed URL patterns, and provide a decision matrix.

## Last updated

2026-02-03

## Off-The-Shelf Reverse Proxies

Option: Use a generic reverse proxy (Nginx/Traefik) in front of providers.

- Nginx provides `proxy_buffering` control and can stream upstream responses without buffering if configured. [Nginx proxy_buffering](https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering)
- Traefik includes a buffering middleware that can buffer request/response bodies and enforce size limits, which is typically undesirable for long-lived streaming responses. [Traefik Buffering Middleware](https://doc.traefik.io/traefik/middlewares/http/buffering/)
- Neither Nginx nor Traefik will rewrite HLS playlist URIs or handle refresh-on-failure by themselves; they only proxy the bytes they receive.

Assessment: Useful for transport and TLS termination, but insufficient for HLS URI rewriting or resolver-driven refresh.

## HLS-Aware Proxy Implementations (Existing Projects)

Option: Adopt or integrate an existing HLS-aware proxy project.

- HLSCachingReverseProxyServer (Java) explicitly rewrites `.m3u8` URLs to the proxy server and caches media resources. [HLSCachingReverseProxyServer](https://github.com/matvp91/HLSCachingReverseProxyServer)
- node-HLS-Proxy (Node.js) advertises HLS proxying that modifies playlists so segment URLs are proxied rather than direct. [HLS-Proxy](https://github.com/warren-bank/HLS-Proxy)
- m3u8-streaming-proxy (Python) advertises proxying and rewriting `.m3u8` streaming URLs. [m3u8-streaming-proxy](https://github.com/kazutoiris/m3u8-streaming-proxy)
- MediaFlow Proxy is positioned as a streaming media reverse proxy that supports HLS, suggesting off-the-shelf proxying and playlist handling. [MediaFlow Proxy](https://github.com/mhdzumair/mediaflow-proxy)

Assessment: These projects validate the playlist rewrite pattern, but differ in language/runtime and may not integrate cleanly with AniBridge’s resolver and auth model.

## Python HLS Parsing Libraries

Option: Use a Python library to parse/rewrite playlists.

- The `m3u8` Python library provides parse/load/dump support for HLS playlists, which can be used to safely modify URI-bearing tags. [m3u8 Python Library](https://github.com/globocom/m3u8)

Assessment: Likely the most maintainable approach for complex tag handling, but must be evaluated against real provider playlists and performance expectations.

## Streaming HTTP Client Options (Python)

Option: Implement proxy streaming in-process using an HTTP client.

- HTTPX supports async streaming via `client.stream()` and `response.aiter_bytes()`. [HTTPX Async Streaming](https://www.python-httpx.org/async/)
- aiohttp supports streaming response iteration via `response.content.iter_chunked()`. [aiohttp Streams](https://docs.aiohttp.org/en/stable/streams.html)

Assessment: Both are viable. HTTPX is already a dependency (`pyproject.toml:34`), which may reduce new dependency surface.

## Signed URL / Auth Patterns

Option: Implement HMAC-signed proxy URLs with expiry.

- HMAC definition and usage are standardized in RFC 2104. [RFC 2104](https://www.rfc-editor.org/rfc/rfc2104)

Assessment: HMAC signing is a standard, library-supported approach for URL authentication.

## Decision Matrix (High-Level)

| Option | Pros | Cons | Effort | Risk | Fit For AniBridge |
| --- | --- | --- | --- | --- | --- |
| In-app proxy + HLS rewrite (custom) | Full control; integrates resolver, cache, refresh | More engineering effort | Medium/High | Medium | High |
| External HLS proxy (Java/Node/Python project) | Proven pattern; faster initial implementation | Runtime mismatch; integration complexity; auth mismatch | Medium | Medium/High | Medium |
| Generic reverse proxy (Nginx/Traefik) | Mature, easy to deploy | No HLS rewrite; no resolver refresh | Low | High (functional gap) | Low |

## Recommendation (Conditional)

Proceed with an in-app proxy and HLS rewrite design unless maintainers explicitly prefer adopting an external HLS proxy project. The existing projects validate feasibility but do not eliminate the need for AniBridge-specific resolver, auth, and refresh logic. [HLSCachingReverseProxyServer](https://github.com/matvp91/HLSCachingReverseProxyServer), [HLS-Proxy](https://github.com/warren-bank/HLS-Proxy), [m3u8-streaming-proxy](https://github.com/kazutoiris/m3u8-streaming-proxy)
