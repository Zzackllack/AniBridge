# Problem Statement

## Status

Draft

## Scope

Define the concrete playback failures in the current STRM flow and why a proxy-stream + HLS rewrite approach is required, backed by existing repo evidence and external protocol specs.

## Last updated

2026-02-03

## Problem Summary

Today, STRM jobs resolve a direct provider/CDN URL and write that URL into the `.strm` file. The STRM file therefore points at a tokenized, provider-resolved URL rather than a stable AniBridge endpoint. Evidence: the STRM job resolves `direct_url` via `get_direct_url_with_fallback`, then writes it into the `.strm` file using `build_strm_content`. See `app/core/scheduler.py:215`, `app/core/scheduler.py:241`, and `app/utils/strm.py:8`.

In VPN/Gluetun deployments, the resolved provider URL is often bound to the resolver’s egress IP/ASN or request headers, and a media server (e.g., Jellyfin) plays it from a different egress, causing 403 responses. This binding risk is documented in existing STRM proxy context notes. See `specs/006-fix-strm-files/context.md:5` and `specs/006-fix-strm-files/HLS-m3u8-context.md:5`.

A simple redirect is insufficient: redirecting to the provider URL still makes the media server hit the CDN directly from its own egress, which reproduces the same IP/ASN binding failure. This is explicitly noted in the proxy context notes. See `specs/006-fix-strm-files/context.md:23` and `specs/006-fix-strm-files/HLS-m3u8-context.md:47`.

## Why HLS Complicates Proxying

Most STRM entries are HLS `.m3u8` playlists (per prior STRM/HLS context notes). HLS playlists are line-based documents containing either tags or URIs, and playlists can be master playlists (referencing variants) or media playlists (referencing segments). [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216) The URIs inside a playlist can be relative to the playlist URL. [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216) This means proxying only the initial `.m3u8` response is insufficient; all nested playlist and segment URIs must be rewritten to point back to AniBridge so the media server never contacts the CDN directly.

HLS also includes URI-bearing tags such as `EXT-X-KEY`, `EXT-X-MAP`, `EXT-X-MEDIA`, `EXT-X-I-FRAME-STREAM-INF`, and `EXT-X-SESSION-KEY`, which must be rewritten to avoid leaking CDN access outside the VPN egress. [RFC 8216](https://www.rfc-editor.org/rfc/rfc8216)

## Why HTTP Range Support Is Mandatory

HTTP Range requests are the standard way clients request partial content and seek within streams. Range semantics and `Accept-Ranges` / `Content-Range` behavior are defined in HTTP semantics. [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110) Streaming proxies must preserve Range behavior to avoid breaking playback and seeking. Jellyfin has documented issues where byte-range requests are not passed through for `.strm` sources, reinforcing that Range handling is critical for STRM playback. [Jellyfin Issue #11676](https://github.com/jellyfin/jellyfin/issues/11676)

## Required Direction (High Level)

The STRM file should point to a stable AniBridge proxy URL, not the provider/CDN. AniBridge must act as a byte-streaming reverse proxy (not a redirect), support HTTP Range, and implement HLS-aware playlist rewriting so that every downstream request is routed back through AniBridge.
