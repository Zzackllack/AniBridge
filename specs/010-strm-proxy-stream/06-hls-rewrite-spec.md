# HLS Rewrite Spec

## Status

Draft

## Scope

Define exact playlist parsing and rewrite rules for HLS `.m3u8` content, including URI-bearing tags, relative URI resolution, loop prevention, and test vectors.

## Last updated

2026-02-03

## Parsing Strategy (Decision Gate)

Option A: Use the Python `m3u8` library for parsing and rendering.

- Rationale: the library supports loading and dumping HLS playlists and provides structured access to tags and URIs. citeturn15view0

Option B: Implement a strict line-based parser that rewrites URI-bearing lines and tag attributes.

- Rationale: avoid dependency, maximize control over output formatting.

Decision gate: choose based on real-world playlist complexity and maintainer appetite for an additional dependency.

## HLS Rewrite Rules (Normative)

HLS playlists are line-oriented and contain a mix of tags (`#EXT-*`) and URI lines; playlists are either master or media playlists. citeturn3view3

### Rule 1: Detect Playlist Type

- If playlist contains `#EXT-X-STREAM-INF` or `#EXT-X-I-FRAME-STREAM-INF`, treat it as a master playlist. citeturn3view3
- Otherwise, treat as a media playlist.

### Rule 2: Rewrite All URI Lines

- Any non-empty, non-`#` line is a URI and must be rewritten to the proxy endpoint.
- Resolve relative URIs against the playlist URL before rewriting. citeturn3view4

### Rule 3: Rewrite URI-Bearing Tags (Exhaustive List)

The following tags contain URI attributes and must be rewritten:

1. `#EXT-X-KEY:URI="..."` for encryption keys. citeturn3view3
2. `#EXT-X-MAP:URI="..."` for init segments. citeturn3view4
3. `#EXT-X-MEDIA:URI="..."` for audio/subtitle renditions. citeturn3view4
4. `#EXT-X-STREAM-INF` followed by a URI line for variant playlists. citeturn3view3
5. `#EXT-X-I-FRAME-STREAM-INF:URI="..."` for I-frame playlists. citeturn3view4
6. `#EXT-X-SESSION-KEY:URI="..."` for session-wide keys. citeturn3view4

### Rule 4: Preserve Non-URI Tags

- Do not modify tags such as `#EXT-X-TARGETDURATION`, `#EXT-X-VERSION`, `#EXTINF`, `#EXT-X-ENDLIST`, or `#EXT-X-BYTERANGE` except as needed to maintain valid playlist structure.

### Rule 5: Avoid Infinite Rewrite Loops

- If a URI already points to the proxy endpoint, do not re-wrap it.
- Add an internal flag (e.g., `proxied=1`) or validate signature/host to detect already-proxied URLs.

### Rule 6: Maintain Query Tokens Exactly

- Preserve upstream query strings and fragments when constructing the signed proxy URL. This avoids breaking tokenized URLs that include TTL or IP/ASN hints.

## Security And Key Handling

- Never log the raw `EXT-X-KEY` URI or key contents.
- Do not cache decrypted key material. Only proxy bytes from the upstream key URI.
- Ensure signed proxy URLs for key requests have short expiries relative to playlist TTL.

## Nested Playlist Handling

- Master playlist rewrite must ensure every child playlist URI points to the proxy.
- Child playlists fetched through the proxy must be rewritten recursively, using the same rules, until leaf segment URIs are all proxy URLs.

## Test Vectors (Synthetic, Derived From Spec)

These examples are synthetic but aligned with RFC 8216 semantics. citeturn3view3turn3view4

### Test Vector 1: Master Playlist

Input:

```m3u8
#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360
low/playlist.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=1400000,RESOLUTION=1280x720
https://cdn.example.com/high/playlist.m3u8
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="English",URI="audio/eng/playlist.m3u8"
```

Expected rewrite (proxy base shown as `https://proxy.example/strm/proxy?u=...`):

```m3u8
#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360
https://proxy.example/strm/proxy?u=<signed://origin/low/playlist.m3u8>
#EXT-X-STREAM-INF:BANDWIDTH=1400000,RESOLUTION=1280x720
https://proxy.example/strm/proxy?u=<signed://cdn.example.com/high/playlist.m3u8>
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="English",URI="https://proxy.example/strm/proxy?u=<signed://origin/audio/eng/playlist.m3u8>"
```

### Test Vector 2: Media Playlist With Key And Init Segment

Input:

```m3u8
#EXTM3U
#EXT-X-VERSION:7
#EXT-X-MAP:URI="init.mp4"
#EXT-X-KEY:METHOD=AES-128,URI="https://keys.example.com/key.bin"
#EXTINF:6.0,
segment001.m4s
#EXTINF:6.0,
segment002.m4s
#EXT-X-ENDLIST
```

Expected rewrite:

```m3u8
#EXTM3U
#EXT-X-VERSION:7
#EXT-X-MAP:URI="https://proxy.example/strm/proxy?u=<signed://origin/init.mp4>"
#EXT-X-KEY:METHOD=AES-128,URI="https://proxy.example/strm/proxy?u=<signed://keys.example.com/key.bin>"
#EXTINF:6.0,
https://proxy.example/strm/proxy?u=<signed://origin/segment001.m4s>
#EXTINF:6.0,
https://proxy.example/strm/proxy?u=<signed://origin/segment002.m4s>
#EXT-X-ENDLIST
```

### Test Vector 3: I-Frame Playlist

Input:

```m3u8
#EXTM3U
#EXT-X-I-FRAME-STREAM-INF:BANDWIDTH=150000,URI="iframe/playlist.m3u8"
```

Expected rewrite:

```m3u8
#EXTM3U
#EXT-X-I-FRAME-STREAM-INF:BANDWIDTH=150000,URI="https://proxy.example/strm/proxy?u=<signed://origin/iframe/playlist.m3u8>"
```
