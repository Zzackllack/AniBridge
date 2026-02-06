# Spec 4: File-Backed Cached Remux for Stable Jellyfin Metadata

## Goal

Fix `Video-Bitrate: 0 kbps` in Jellyfin for STRM playback **without** introducing playback duration regressions (e.g. 6-second timeline, auto-next-episode).

## Scope

In scope:

- `/strm/stream` behavior for HLS upstreams.
- Remux strategy and cache lifecycle inside AniBridge.
- Fallback behavior when remux cannot be produced.
- Observability and tests.

Out of scope:

- Jellyfin source code changes.
- Non-HLS provider transport redesign.
- Long-term offline transcoding pipeline.

## Problem Summary

Current pure playlist approach preserves HLS behavior but Jellyfin still often reports `Video-Bitrate: 0 kbps` because ffprobe on HLS commonly lacks per-video `bit_rate`.

Previous pipe-based remux fixed bitrate display but caused unstable playback semantics in practice (timeline/duration regressions and early stop behavior).

## Decision

Use **file-backed cached remux** instead of piping remux bytes directly.

Key idea:

1. Resolve upstream HLS URL.
2. Build a deterministic cache key per episode/provider/upstream signature.
3. If a completed remux artifact exists, serve that artifact directly.
4. If missing/stale, produce remux into a cache directory using ffmpeg.
5. Expose remux artifact as stable file-based stream to Jellyfin.

This keeps bitrate metadata behavior from remux while avoiding fragile live pipe semantics.

## Architecture

### Components

- `RemuxCacheManager`
  - Computes cache keys.
  - Tracks artifact state (`missing`, `building`, `ready`, `failed`, `expired`).
  - Handles lock files to prevent duplicate work.
- `RemuxWorker`
  - Runs ffmpeg remux job to on-disk target.
  - Writes to temp file and atomically renames on success.
- `STRM Stream Route Integration`
  - Chooses between cached remux response and fallback HLS rewrite path.

### Cache Storage

- Directory: configurable (default under `DATA_DIR`, not committed).
- Artifact type:
  - Preferred: remuxed MP4 file for straightforward metadata probing.
  - Optional variant: remuxed local HLS package if MP4 proves less stable for large files.
- State files:
  - `<key>.lock` while building
  - `<key>.meta.json` build metadata, source URL fingerprint, timestamps, size, probe result
  - `<key>.mp4` final artifact

### Cache Key

Should include:

- Identity: site, slug, season, episode, language, provider.
- Upstream URL fingerprint (host + normalized path + relevant query hash).
- Remux config version (to invalidate when ffmpeg args change).

## End-to-End Flow

1. Request enters `/strm/stream`.
2. Resolve upstream URL as currently done.
3. Detect HLS.
4. Check remux cache:
   - `ready` -> stream cached artifact.
   - `building` -> short wait + retry; if still building, return controlled fallback.
   - `missing/expired/failed` -> attempt build with lock.
5. Build process:
   - ffmpeg input = upstream HLS URL.
   - write temp file.
   - validate output with ffprobe (duration > threshold, video stream present, bitrate present or inferable).
   - atomically promote to final artifact + write metadata.
6. Serve artifact response with stable headers.
7. On any hard failure, fallback to existing HLS playlist rewrite path.

## ffmpeg Strategy (Initial)

Objectives:

- Do not encode video unless necessary.
- Produce deterministic output with valid moov/metadata.

Baseline direction:

- `-c:v copy` when possible.
- Audio either copy or normalize only if container requires it.
- File output (not `pipe:1`).
- Avoid fragmented stream-first flags that can distort probing semantics for this use case.

Exact args should be finalized during implementation spike with two validation checks:

- Jellyfin reports non-zero video bitrate.
- Episode duration and timeline remain correct.

## Fallback Behavior

Fallback must always preserve playback:

- If remux build fails or times out, return rewritten HLS playlist path.
- Mark artifact as `failed` with cool-down to avoid immediate repeated builds.
- Keep user-visible playback available even when metadata fix is unavailable.

## Concurrency and Safety

- Single-builder lock per cache key.
- Additional requests can:
  - wait briefly for build completion, then serve artifact, or
  - immediately use fallback path after timeout threshold.
- Temp files cleaned on startup and periodically.
- Build timeout enforced to prevent hung ffmpeg workers.

## Configuration

Add/adjust settings:

- `STRM_PROXY_HLS_REMUX_CACHED_ENABLED` (bool, default false initially).
- `STRM_PROXY_HLS_REMUX_CACHE_DIR`.
- `STRM_PROXY_HLS_REMUX_CACHE_TTL_SECONDS`.
- `STRM_PROXY_HLS_REMUX_BUILD_TIMEOUT_SECONDS`.
- `STRM_PROXY_HLS_REMUX_MAX_CONCURRENT_BUILDS`.
- `STRM_PROXY_HLS_REMUX_FAIL_COOLDOWN_SECONDS`.

Rollout recommendation:

- Ship behind feature flag.
- Enable for targeted users/instances first.

## Observability

Log fields:

- cache key, source fingerprint, remux state, build duration, output size.
- fallback reason (`timeout`, `ffmpeg_error`, `probe_invalid`, `lock_wait_exceeded`).

Metrics:

- remux build success/failure counts.
- cache hit ratio.
- average build time.
- fallback rate.

## Validation Plan

Functional:

- Jellyfin player info shows non-zero video bitrate.
- Correct episode duration and timeline behavior.
- No premature playback stop/auto-next regression.

Load:

- Concurrent requests for same episode only spawn one builder.
- Different episodes respect max concurrent builders.

Resilience:

- Simulate upstream errors during build.
- Simulate ffmpeg failure and verify fallback path.
- Restart during build and verify cleanup/recovery.

## Test Plan

Unit tests:

- cache key generation and invalidation.
- lock acquisition/release behavior.
- remux metadata state transitions.

Integration tests:

- `/strm/stream` serves cached artifact when present.
- build-on-miss then serve artifact.
- fallback when build fails.

Regression tests:

- Existing HLS rewrite behavior unchanged when feature disabled.

## Risks and Mitigations

Risk: Disk growth due to cached artifacts.  
Mitigation: TTL + LRU cleanup + max cache size enforcement.

Risk: Build latency on first request.  
Mitigation: short wait + fallback, optional background prewarm.

Risk: Provider URL churn invalidates artifacts quickly.  
Mitigation: include source fingerprint and use moderate TTL.

Risk: ffmpeg incompatibility across environments.  
Mitigation: startup capability check + explicit log warning + auto fallback.

## Migration / Rollout

Phase 1:

- Implement behind disabled flag.
- Add tests and observability.

Phase 2:

- Enable in staging with Jellyfin playback verification.

Phase 3:

- Enable in production for selected users.
- Monitor fallback/build-failure rates.

Phase 4:

- Make default only after stable metrics and no timeline regressions.

## Recommendation

Proceed with file-backed cached remux behind a feature flag.  
This is the most realistic no-fork path to reliably improve Jellyfin bitrate metadata while preserving playback stability.
