Coding Plan
Approach

    Add missing HLS v7+ tags with URI attributes (#EXT-X-PRELOAD-HINT, #EXT-X-RENDITION-REPORT, #EXT-X-SESSION-DATA) for improved compatibility with modern streaming features
    Add explicit tests proving BANDWIDTH and metadata preservation to prevent regression and demonstrate correct behavior
    Document HTTPS/reverse proxy requirements as the primary fix for Direct Play failures caused by mixed content blocking
    Document bitrate detection behavior to set correct expectations about what AniBridge can and cannot control

Observations

The AniBridge application provides an HLS proxy (app/core/strm_proxy/) that rewrites HLS playlists to route all requests through its authentication layer. The hls.py module performs line-by-line rewriting, handling tags with URI attributes via_URI_TAG_PREFIXES and standalone URI lines separately. The #EXT-X-STREAM-INF tag (which contains BANDWIDTH) is correctly preserved unchanged since its URI appears on the following line. CORS is already configured with permissive defaults. Tests exist in tests/test_strm_hls_rewrite.py but don't explicitly verify metadata preservation.
Assumptions
Assumption 1: Root cause of 0 kbps video bitrate

Options Considered:

    Add #EXT-X-STREAM-INF to _URI_TAG_PREFIXES as the ticket suggests
    Focus on adding legitimately missing HLS tags with URI attributes, comprehensive tests, and documentation about the actual constraints (HTTPS requirement, FFmpeg probing limitations)

Chosen Option: 2

Rationale: The #EXT-X-STREAM-INF tag does not have a URI attribute, so adding it to _URI_TAG_PREFIXES would have no effect. The 0 kbps issue is likely caused by FFmpeg probing behavior or mixed content blocking, not HLS rewriting. We'll add truly missing tags, prove metadata preservation with tests, and document the actual requirements.
