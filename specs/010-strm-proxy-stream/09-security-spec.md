# Security Spec

## Status

Draft

## Scope

Define threat model, auth/signing options, SSRF protections, and logging redaction rules for the STRM proxy endpoints.

## Last updated

2026-02-03

## Threat Model

- Open proxy abuse (unauthenticated use to proxy arbitrary URLs).
- SSRF via `u=` or playlist URIs to internal networks or metadata endpoints. [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
- Token leakage in logs or analytics.
- Replay attacks against signed URLs if expiry is too long.
- Key URI leakage from HLS (`EXT-X-KEY`). [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)

## Auth Options (Draft)

1. `none`: no auth; only acceptable for trusted LAN deployments.
2. `apikey`: reuse existing API key model; token passed as query param.
3. `token` (HMAC signed URLs): sign query parameters with expiry using HMAC (RFC 2104). [RFC 2104](https://www.rfc-editor.org/rfc/rfc2104)

## Recommended Default (Conditional)

- Default to `token` in WAN or unknown exposure scenarios; allow `none` only when explicitly set.
- Decision gate: maintainers must confirm expected exposure model and usability constraints.

## HMAC Signing Scheme (Draft)

- Inputs to sign: canonical query string (`site`, `slug`, `s`, `e`, `lang`, `provider`, `exp`, optional `u`).
- Signature: `HMAC-SHA256(secret, canonical_string)` (exact algorithm to be confirmed).
- Expiry: integer timestamp seconds; reject expired tokens.

## SSRF Protections (Draft)

- Validate that upstream URLs are HTTP(S) only.
- Optionally enforce allowlist of provider domains.
- Block requests to private IP ranges, loopback, or link-local metadata endpoints (decision gate). [OWASP SSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)

## Logging Redaction Rules

- Never log full upstream URLs; log only host + path hash.
- Redact query parameters like `token`, `sig`, `exp`, and any `u` parameter.
- For HLS, never log key URIs or key response bodies.

## Token Storage And Rotation

- Store proxy secret only in environment variables.
- Support rotation by accepting multiple active secrets (decision gate).

## Security-Related Decision Gates

- Whether to include client IP in HMAC scope (bind tokens to client IP).
- Whether to allow unsigned access for requests from RFC1918 networks.
- Whether to persist upstream URLs in a mapping table and for how long.
