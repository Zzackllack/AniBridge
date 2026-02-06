# Spec 3: Playback Regression Analysis After HLS->fMP4 Remux

## 1) Objective

Fix the original Jellyfin metadata bug (`Video-Bitrate: 0 kbps`) **without**
introducing playback regressions (short timeline, wrong episode duration,
automatic next-episode trigger).

This document analyzes the current remux approach behavior and defines the
constraints any final solution must satisfy.

## 2) Observed Behavior

From user report and AniBridge runtime log:

- `Video-Bitrate` now shows correctly in Jellyfin player/media info.
- New regressions:
  - playback timeline shows about 6 seconds,
  - episode list duration appears around 1 minute,
  - playback advances to next episode after timeline end.
- AniBridge log (`data/terminal-2026-02-06_21-10-44-2229f8ea.log`) shows:
  - HLS input is detected,
  - remux process starts and succeeds repeatedly,
  - no explicit remux failure/timeouts.

## 3) Current Technical State

Current `/strm/stream` behavior for HLS input:

1. Detect HLS.
2. Spawn ffmpeg remux process.
3. Serve fragmented MP4 bytes directly from `stdout` (`pipe:1`).
4. Return `Content-Type: video/mp4`.

This solved one metric (bitrate visibility) but changed transport semantics from
playlist-driven HLS VOD to pipe-driven fragmented MP4.

## 4) Most Likely Root Cause

Most likely failure mode is **container/timeline semantics mismatch**:

- Jellyfin expects stable duration semantics for episode playback logic.
- Pipe-fragmented MP4 can expose partial/unstable duration metadata at probe
  time.
- Jellyfin appears to make decisions (UI timeline, auto-next, library duration)
  from early probe data that does not represent full runtime.

Why this hypothesis is strong:

- Regression started exactly after changing to streamed fMP4 remux path.
- AniBridge logs show successful remux startup, so this is not a fetch failure.
- Symptoms are duration-related, not decode-related.

## 5) Why the Current Approach Is Risky for Production

The current approach optimizes one metric (stream bitrate) by changing the media
delivery model globally for HLS sources. This has broad side effects:

- Player timeline/seek behavior can diverge by client.
- Episode auto-advance logic can trigger incorrectly.
- Library scanner/prober may cache wrong duration.
- Behavior can vary between Jellyfin versions and clients.

Conclusion: **as currently implemented, this should not be considered production
safe**.

## 6) Required Functional Guarantees (Hard Requirements)

Any accepted solution must satisfy all:

1. Jellyfin must no longer show `Video-Bitrate: 0 kbps` for affected streams.
2. Episode runtime shown in library view must match actual episode runtime
   (within normal probe tolerance).
3. Player timeline must track real progress (no forced 6-second end).
4. Playback must not auto-switch to next episode early.
5. Fallback path must preserve previous known-good playback behavior.
6. Failure of enhancement path must degrade gracefully (no playback break).

## 7) Constraints

- Most providers are HLS; solution cannot depend on non-HLS providers.
- No large persistent artifact storage under `data/` for temporary media blobs.
- Startup latency should remain acceptable for interactive playback.
- Must remain compatible with STRM proxy auth and current caching behavior.

## 8) Non-Goals

- Eliminating all transcoding scenarios in Jellyfin.
- Solving mixed-content/network-reachability in this spec iteration.
- Reworking provider selection/resolution logic.

## 9) Decision Criteria

The chosen architecture should maximize:

- playback correctness,
- metadata correctness,
- operational simplicity,
- rollback safety.

The solution should avoid globally changing container semantics unless timeline
metadata is demonstrably stable across Jellyfin probe + playback phases.

## 10) Additional Evidence Needed Before Final Implementation

To reduce execution risk when implementing next phase:

- Jellyfin server log lines around item probe and playback-start for one
  affected episode.
- Jellyfin ffmpeg transcode/probe log for the remuxed stream case.
- One sample of media info before/after cache refresh for the same episode.
- Confirmation whether issue reproduces across at least two clients
  (web + native app).

