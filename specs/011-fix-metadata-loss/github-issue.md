# [BUG] Metadata Loss (0 kbps Bitrate) and Forced Transcoding due to HLS Handling & Mixed Content* #51

### **Description**

When using AniBridge to stream content to **Jellyfin**, several issues occur that prevent a smooth playback experience. Most notably, Jellyfin fails to detect the stream's bitrate (reports **0 kbps**), which leads to the server forcing a low-quality transcode (limited to ~420 kbps) even when the source is 720p/1080p.

Additionally, **Direct Play** often fails in browser-based clients, forcing the Jellyfin server to transcode the HLS stream unnecessarily.

### **Symptoms in Jellyfin**

* **Bitrate Detection:** The "Media Info" panel in Jellyfin shows `Video-Bitrate: 0 kbps`.
* **Quality Limitation:** In the player settings, the user can only select a bitrate of **420 kbps** or lower because Jellyfin assumes the source has no bandwidth.
* **Forced Transcoding:** The playback info states: *"Reason for transcoding: There was an error starting direct playback."*
* **Visual Artifacts:** If Hardware Acceleration (VAAPI/NVENC) is used, the extremely low target bitrate (calculated from the 0 kbps source) causes significant macro-blocking or a "pixelated mess."

```text
Wiedergabe-Informationen
    Player: Html Video Player
    Abspielmethode: Transkodierung
    Protokoll: https
    Streamtyp: HLS
    Videoinformationen
        Playerabmessungen: 2560 × 1271
        Videoauflösung: 1280 × 720
        Ausgelassene Frames: 0
        Fehlerhafte Frames: 0
    Transkodierungsinfo
        Videocodec: H264
        Audiocodec: AAC (direct)
        Audiokanäle: 2
        Bitrate: 256 kbps
        Fortschritt der Transkodierung: 47.8 %
        Bildrate der Transkodierung: 250 fps (10.42×)
        Grund für Transkodierung: Es gab einen Fehler beim Start der Direktwiedergabe
    Original Medium-Information
        Container: hls
        Größe: 162.0 Bytes
        Bitrate: 192 kbps
        Videocodec: H264 High
        Video-Bitrate: 0 kbps
        Video-Dynamikumfang: SDR
        Audiocodec: AAC LC
        Audio-Bitrate: 192 kbps
        Audiokanäle: 2
        Audio-Abtastrate: 44100 Hz
```

### **Technical Analysis & Root Causes**

#### **1. Metadata Loss in `hls.py`**

In `app/core/strm_proxy/hls.py`, the `_URI_TAG_PREFIXES` list is missing critical HLS tags used in Master Playlists.
Specifically, the **`#EXT-X-STREAM-INF`** tag is not being rewritten. This tag contains the `BANDWIDTH` and `RESOLUTION` attributes.
Because Jellyfin/FFmpeg cannot see these attributes through the proxy, it defaults to `0 kbps`.

#### **2. Protocol Mismatch (Mixed Content)**

AniBridge typically runs on `http://[IP]:8083`. If the Jellyfin server is secured via **HTTPS**, modern browsers block "Mixed Content."

* **The Conflict:** An HTTPS site (Jellyfin) cannot directly load an HTTP stream (AniBridge) into the HTML5 Video Player.
* **The Result:** The browser rejects the direct stream link, and Jellyfin falls back to server-side transcoding to "bridge" the connection, wasting CPU/GPU resources.

#### **3. Missing URI Rewriting**

The current regex/tag-prefix approach in `hls.py` is quite restrictive. If a provider uses HLS tags not listed in `_URI_TAG_PREFIXES` (like Session keys or complex variant streams), the URLs remain pointing to the original CDN, which usually fails due to missing headers/cookies/CORS when requested directly by the client.

### **Proposed Documentation Update**

It should be explicitly noted in the documentation (Requirements/Setup) that:

> **Direct Play Requirement:** To enable Direct Play, the AniBridge proxy **must** be exposed via the same protocol (and ideally the same domain/subdomain) as Jellyfin. If Jellyfin is served over HTTPS, AniBridge must also be behind a **Reverse Proxy with HTTPS**. Otherwise, browser security policies will block the stream and force server-side transcoding.

### **Potential Improvements**

1. **Expand `_URI_TAG_PREFIXES`:** Add `#EXT-X-STREAM-INF` to ensure Master Playlists are correctly proxied with bitrate data.
2. **Bitrate Injection:** If the upstream bitrate is known during resolution, it could be injected into the proxied manifest.
3. **CORS Headers:** Ensure the proxy server sends permissive CORS headers (`Access-Control-Allow-Origin: *`) to allow web players to fetch segments.

### **Environment Info**

* **AniBridge Version:** 2.2.0
* **Jellyfin Version:** 10.11.6
* **Client:** Chrome
