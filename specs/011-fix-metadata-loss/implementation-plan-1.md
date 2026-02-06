Task: 1

This phase improves HLS playlist rewriting by adding missing tag support and
expanding test coverage.

**Goal:** Ensure all HLS tags with `URI=` attributes are correctly rewritten and
properly tested.

**Implementation steps:**

1. **Add `#EXT-X-SESSION-DATA` tag support in `app/core/strm_proxy/hls.py`:**
   - Locate the `_URI_TAG_PREFIXES` tuple
   - Add `"#EXT-X-SESSION-DATA"` to the tuple

- This tag follows the same `URI="..."` pattern as other tags in the list and is
used for external session metadata

2. **Expand test coverage in `tests/test_strm_hls_rewrite.py`:**
   - Add test case for `#EXT-X-I-FRAME-STREAM-INF` tag with `URI=` attribute
   - Add test case for `#EXT-X-SESSION-KEY` tag with `URI=` attribute
   - Add test case for the newly added `#EXT-X-SESSION-DATA` tag

- Consider adding edge case tests for URIs with query parameters to ensure they
are preserved correctly during rewriting
===============================================================================

Task: 2

This phase documents HTTPS requirements for Direct Play functionality to help
users avoid mixed content issues.

**Goal:** Provide comprehensive documentation explaining why HTTPS is required
for Direct Play and how to troubleshoot related issues.

**Implementation steps:**

1. **Update `docs/src/api/strm-proxy.md` with HTTPS requirements:**
   - Add a "Direct Play Requirements" section
   - Explain why HTTPS is required (mixed content blocking in browsers)

- Clarify that AniBridge must be served over HTTPS if Jellyfin/Plex/Emby uses
HTTPS
  - Include brief reverse proxy guidance with examples (nginx/Traefik/Caddy)
- Emphasize that without HTTPS, browsers block the stream and media servers fall
back to transcoding

2. **Add FAQ entries in `docs/src/guide/faq.md`:**

- "Why does Jellyfin show 0 kbps bitrate?" - Explain this may be Jellyfin probe
behavior
  - "Why doesn't Direct Play work?" - Explain HTTP vs HTTPS requirement
- "Do I need a reverse proxy for AniBridge?" - Answer yes, if using HTTPS media
server

3. **Add troubleshooting entries in `docs/src/guide/troubleshooting.md`:**
   - Direct Play failures with HTTP/HTTPS mismatch
   - Browser mixed content errors
   - Forced transcoding despite high-quality source

4. **Update configuration documentation:**

- In `docs/src/guide/configuration.md`, add a note in the STRM section about
HTTPS requirement for Direct Play
- In `docs/src/api/environment.md`, clarify that `STRM_PUBLIC_BASE_URL` should
use HTTPS when the media server uses HTTPS
