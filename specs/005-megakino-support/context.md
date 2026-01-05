### **Description**

We should add support for **megakino** as an additional provider alongside the existing *s.to* and *aniworld.to* sources.

Currently AniBridge pulls content primarily from these providers, which works well but adding *megakino* would expand available content (not just anime but also live-action series). The challenge is that *megakino* domains are highly unstable and frequently rotate between different TLDs (e.g., `.lol`, `.cx`, `.ms`, `.video`, etc.), so any implementation must handle dynamic domain resolution, not just a hardcoded URL.

### **Proposed Implementation**

#### **Provider Discovery**

1. Implement logic to dynamically resolve the **current valid megakino domain** domains change often, so we can’t hardcode a single URL.

   * Possible strategies include simple domain fallbacks, DNS resolution checks, or predefined candidate list + health-checking.
2. Abstract domain resolution into the provider interface so it fits the existing provider system cleanly.

#### **Integration**

3. Use the existing **Megakino-Downloader** project as a starting point for parsing and downloading content.

   * *Megakino-Downloader* project exists on [GitHub](https://github.com/Tmaster055/Megakino-Downloader) as a reference for scraping/downloading logic.
   * However, its URL is static and likely outdated needs integration into a dynamic lookup flow.
4. Map download logic into AniBridge’s current content ingestion pipeline (similar to how s.to / aniworld are handled).
5. Downloading itself should leverage the current tooling (e.g., `yt-dlp`like just the existing downloader abstraction in AniBridge) so integration is straightforward.

### **Technical Considerations**

* Domain rotation / discovery is the core blocker needs a robust resolution strategy rather than hardcoding a specific domain.
* Ensure provider module maintains consistency with AniBridge’s existing provider API and error handling.

### **Out of Scope**

* Any attempt to rebrand the project around megakino this is purely additive.
* User-facing provider selection UI (future enhancement only).

<!-- When you are implementing the megakino support, look at findings.md -->
