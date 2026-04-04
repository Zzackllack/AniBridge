# STRM Proxy Stream Specification Set

## Status

Draft

## Scope

Define a spec-only, research-backed design for converting STRM playback from provider/CDN direct URLs to stable AniBridge proxy URLs, including byte-proxy streaming, HTTP Range support, HLS playlist rewriting, refresh-on-failure, security, caching, and a future persistence path.

## Last updated

2026-02-03

## Overview

This spec set formalizes the STRM proxy-stream direction documented in `specs/010-strm-proxy-stream/github-issue.md` and the earlier STRM proxy concepts in `specs/006-fix-strm-files/context.md` and `specs/006-fix-strm-files/HLS-m3u8-context.md`. It is intentionally spec-only and does not change runtime behavior.

## Navigation

- [00 Problem Statement](00-problem-statement.md)
- [01 Current State Analysis](01-current-state-analysis.md)
- [02 Requirements](02-requirements.md)
- [03 Questions For Maintainers](03-questions-for-maintainers.md)
- [04 Options And Ecosystem Scan](04-options-and-ecosystem-scan.md)
- [05 Proposed Architecture](05-proposed-architecture.md)
- [06 HLS Rewrite Spec](06-hls-rewrite-spec.md)
- [07 Range And Streaming Spec](07-range-and-streaming-spec.md)
- [08 Refresh On Failure Spec](08-refresh-on-failure-spec.md)
- [09 Security Spec](09-security-spec.md)
- [10 Caching And Persistence Spec](10-caching-and-persistence-spec.md)
- [11 Implementation Plan Checklist](11-implementation-plan-checklist.md)
- [12 Test Plan](12-test-plan.md)

## Non-goals

- Implementing any runtime behavior or migrations in this repo.
- Altering current STRM generation, resolver logic, or download behavior.
- Providing a definitive production configuration without maintainer input.

## Glossary

- STRM: A plain-text file containing a single HTTP(S) URL used by media servers for playback.
- HLS: HTTP Live Streaming, a playlist-based streaming format using `.m3u8` playlists and segment files. [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)
- Range: HTTP byte range requests enabling partial content retrieval (e.g., seeking). [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110)
- Master playlist: HLS playlist that references variant playlists. [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)
- Media playlist: HLS playlist that references media segments. [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)
- Segment: Individual media chunk referenced by a media playlist (e.g., `.ts`, `.m4s`). [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)
- Init segment: Initialization data referenced via `EXT-X-MAP`. [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)
