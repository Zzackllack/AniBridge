Coding Plan
Approach

    Clarify that #EXT-X-STREAM-INF is already handled correctly (uses next-line URIs, not URI= attributes) rather than implementing the ticket's incorrect proposed fix
    Add the actually missing #EXT-X-SESSION-DATA tag to the URI rewriting logic
    Improve test coverage for implemented but untested HLS tags
    Document the HTTPS requirement for Direct Play, addressing the mixed content issue that causes browsers to block HTTP streams on HTTPS sites

Observations

The AniBridge strm_proxy module handles HLS playlist rewriting through app/core/strm_proxy/hls.py, which uses a _URI_TAG_PREFIXES tuple for tags containing URI= attributes and separately handles standalone URI lines (like those following #EXT-X-STREAM-INF). CORS is already implemented globally via Starlette middleware in app/cors.py. Documentation lives in docs/src/ with guides, API references, and integration docs. Tests for HLS rewriting exist in tests/test_strm_hls_rewrite.py but have gaps for some implemented tags.
Assumptions
Assumption 1: The ticket's diagnosis about `#EXT-X-STREAM-INF` requires clarification

Options Considered:

    Add #EXT-X-STREAM-INF to _URI_TAG_PREFIXES as the ticket suggests
    Recognize that #EXT-X-STREAM-INF is already handled correctly (uses next-line URIs, not URI= attributes) and focus on the actual missing tag (#EXT-X-SESSION-DATA)

Chosen Option: 2

Rationale: The #EXT-X-STREAM-INF tag does NOT contain a URI= attribute—it uses next-line URIs which the current implementation already handles correctly by treating non-comment lines as standalone URIs. The existing test test_rewrite_hls_master_playlist confirms this works. Adding it to _URI_TAG_PREFIXES would cause the regex to incorrectly search for URI= in the tag line. The actual missing tag from the HLS spec is #EXT-X-SESSION-DATA.
Assumption 2: The 0 kbps video bitrate issue may be a Jellyfin-specific behavior

Options Considered:

    Implement bitrate injection into the proxied manifest
    Document that this may be a Jellyfin probe behavior unrelated to AniBridge's HLS handling

Chosen Option: 2

Rationale: The BANDWIDTH attribute in #EXT-X-STREAM-INF is already preserved (the tag line passes through unchanged). The small playlist size (162 bytes) suggests Jellyfin may be probing a media playlist rather than the master playlist. Bitrate injection would add significant complexity and may not address the root cause, which appears to be Jellyfin's internal stream probing behavior.
