Task: 1

Enhance HLS tag support by adding missing HLS v7+ tags and create comprehensive
tests to verify metadata preservation.

**Task 1: Update HLS Tag Support**

- Locate `_URI_TAG_PREFIXES` in `app/core/strm_proxy/hls.py`
- Add the following HLS v7+ tags to the tuple:
  - `#EXT-X-PRELOAD-HINT` (for low-latency HLS preload hints)
  - `#EXT-X-RENDITION-REPORT` (for low-latency HLS rendition reports)
  - `#EXT-X-SESSION-DATA` (for session-level data with URI)
- These tags contain URI attributes that need to be rewritten for proper proxy
functionality

**Task 2: Add Metadata Preservation Tests**

- Open `tests/test_strm_hls_rewrite.py`
- Add a new test that verifies BANDWIDTH values are preserved:
- Create a test playlist containing `#EXT-X-STREAM-INF` with BANDWIDTH attribute
(e.g., `BANDWIDTH=938338`)
  - Process the playlist through the rewriter
  - Assert the exact BANDWIDTH value appears in the rewritten output
- Add a test case using real-world playlist structure from
`specs/010-strm-proxy-stream/Examples/`:
  - Include attributes like CODECS, FRAME-RATE, VIDEO-RANGE, and RESOLUTION
  - Verify all these attributes are preserved unchanged
- Add a test case for the newly added HLS tags:
- Create test playlists containing `#EXT-X-PRELOAD-HINT`,
`#EXT-X-RENDITION-REPORT`, and `#EXT-X-SESSION-DATA` with URI attributes
- Verify that the URIs in these tags are properly rewritten while the rest of
the tag remains unchanged
===============================================================================

Task: 2

Add comprehensive documentation explaining Direct Play requirements and bitrate
detection behavior.

**Task 1: Document HTTPS/Reverse Proxy Requirements**

- Locate or create appropriate documentation file (`docs/src/api/strm-proxy.md`
or setup guide)
- Add a new section explaining Direct Play requirements:
- Explain that when Jellyfin is served over HTTPS, AniBridge must also be served
over HTTPS
- Document that browsers enforce mixed content blocking (HTTPS pages cannot load
HTTP resources)
- Explain that mixed content blocking causes Jellyfin to fall back to
server-side transcoding instead of Direct Play
- Provide reverse proxy configuration examples:
  - Include nginx configuration example
  - Include Caddy configuration example
  - Include Traefik configuration example
  - Show how each proxy should expose AniBridge over HTTPS
- Document the `STRM_PUBLIC_BASE_URL` configuration:
  - Explain it must be set to the HTTPS URL when using a reverse proxy
  - Provide example values

**Task 2: Document Bitrate Detection Behavior**

- Add a section to the STRM proxy documentation explaining bitrate detection:
  - Explain that Jellyfin delegates HLS parsing to FFmpeg
  - Document that FFmpeg reads BANDWIDTH from HLS master playlists
- Clarify that AniBridge preserves all HLS metadata unchanged (BANDWIDTH,
RESOLUTION, CODECS)
- Document known limitations:
- Explain that if upstream providers serve media playlists directly without a
master playlist, FFmpeg won't have variant bitrate information
- Clarify the distinction between total BANDWIDTH (in HLS metadata) and video
bitrate (from codec-level metadata in segments)
  - Note that AniBridge cannot modify codec-level metadata in video segments
