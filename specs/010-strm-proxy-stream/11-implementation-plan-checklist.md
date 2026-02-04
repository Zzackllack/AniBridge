# Implementation Plan Checklist

## Status

Draft

## Scope

Provide a step-by-step implementation plan for future work, including acceptance criteria and rollout/feature flags.

## Last updated

2026-02-03

## Step-By-Step Plan (Future Work)

1. Confirm maintainer answers for all open questions in `03-questions-for-maintainers.md`.
2. Decide endpoint layout (single `/strm/stream` vs separate HLS endpoints) and finalize query parameter contract.
3. Add new configuration knobs and document them (e.g., `STRM_PROXY_MODE`, `STRM_PUBLIC_BASE_URL`, `STRM_PROXY_AUTH`, `STRM_PROXY_SECRET`, `STRM_PROXY_CACHE_TTL_SECONDS`).
4. Implement proxy endpoints using streaming HTTP client (HTTPX or aiohttp) and `StreamingResponse`.
5. Implement HLS detection and playlist rewrite logic covering all URI-bearing tags.
6. Add Range handling and header pass-through rules per RFC 9110.
7. Add auth/signing validation and logging redaction.
8. Add in-memory cache with TTL and refresh-on-failure logic.
9. Optionally add persistence (StrmUrlMapping) once migration plan is approved.
10. Update docs and configuration guides for STRM proxy mode and HLS behavior.

## Acceptance Criteria (Mapped To Tests)

1. STRM proxy URLs are generated and point to AniBridge when `STRM_PROXY_MODE=proxy`.
2. Playback succeeds when Jellyfin is outside VPN and AniBridge is inside VPN.
3. Range requests return `206` with correct `Content-Range` when upstream supports Range.
4. HLS playlists are rewritten so that all segment, key, and child playlist URIs route back through AniBridge.
5. Refresh-on-failure retries once and then fails fast on repeated errors.
6. Auth token validation blocks unsigned access when enabled.

## Rollout Plan And Feature Flags

- Feature flag: `STRM_PROXY_MODE=direct|proxy|redirect` (default `direct`).
- Feature flag: `STRM_PUBLIC_BASE_URL` (required when proxy mode is enabled).
- Feature flag: `STRM_PROXY_AUTH=none|token|apikey` (default `token` for WAN; `none` for LAN by explicit opt-in).
- Optional flag: `STRM_PROXY_CACHE_TTL_SECONDS`.
- Backward compatibility: existing `.strm` files remain valid under `direct` mode; new proxy mode should be opt-in to avoid breaking existing deployments.

## Migration Plan For Existing STRM Files

- Document a manual regeneration path (delete and re-trigger STRM jobs) or provide a future CLI for bulk rewrite.
- Decide whether to auto-regenerate `.strm` files on first proxy playback request (decision gate).
