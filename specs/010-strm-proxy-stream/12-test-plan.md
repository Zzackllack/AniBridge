# Test Plan

## Status

Draft

## Scope

Define unit, integration, and end-to-end test coverage for STRM proxy streaming, HLS rewriting, Range handling, refresh-on-failure, and security.

## Last updated

2026-02-03

## Unit Tests

1. Range parsing: validate `Range` header parsing and response selection (`200`, `206`, `416`) per RFC 9110. citeturn2view2turn2view3
2. HLS rewrite: rewrite URI lines and tag URI attributes (`EXT-X-KEY`, `EXT-X-MAP`, `EXT-X-MEDIA`, `EXT-X-STREAM-INF`, `EXT-X-I-FRAME-STREAM-INF`, `EXT-X-SESSION-KEY`) per RFC 8216. citeturn3view3turn3view4
3. URL signing: generate and verify HMAC signatures with expiry (RFC 2104). citeturn16view0
4. Cache behavior: TTL expiry, invalidation on refresh-eligible failures.

## Integration Tests

1. Proxy streaming: use a local upstream server with large binary payloads and verify streaming without buffering.
2. HLS proxy: use a fixture HLS playlist with nested variant playlists, key URIs, and init segments; verify all URIs are rewritten.
3. Refresh-on-failure: simulate upstream 403/404 responses and verify single re-resolve + retry.
4. Auth: verify unsigned requests are rejected when `STRM_PROXY_AUTH=token` and accepted when `none`.

## End-To-End Tests (Docker Compose)

1. Use the dev compose stack (`docker-compose.dev.yaml`) with Jellyfin, Sonarr, Prowlarr, and AniBridge.
2. Add Gluetun sidecar and set `network_mode: service:gluetun` per quickstart guidance to reproduce egress mismatch. See `docs/src/guide/quickstart.md:62`.
3. Generate STRM files and confirm playback succeeds from Jellyfin while AniBridge remains behind VPN.
4. Seek/scrub in Jellyfin and verify `206 Partial Content` with proper `Content-Range` is returned. citeturn2view2

## Reproducing IP/ASN Mismatch

1. Run AniBridge with VPN egress (Gluetun) and Jellyfin without VPN.
2. Generate a STRM with direct provider URL (current mode) and confirm 403 playback failure.
3. Switch to proxy mode and confirm playback success with the same episode.

## Performance Tests

1. Sustained playback with multiple concurrent streams.
2. Large HLS segment loads and key fetches with cache hits vs misses.
3. Memory profiling to ensure streaming does not buffer entire responses.
