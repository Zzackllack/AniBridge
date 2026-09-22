# Runtime integration and contract inventory

All repository paths are relative to the AniBridge repository root. Source observations refer to the base commit in the evidence document. Recheck line numbers after implementation; the symbols and responsibility descriptions are the durable anchors.

## Runtime map

```text
Torznab request
  -> title_resolver / CatalogProvider / metadata and specials mapping
  -> availability cache / optional build_episode and quality probing
  -> Torznab XML with stable identity and synthetic download payload

qBittorrent-compatible add
  -> parse magnet or payload -> ClientTask / job -> scheduler
  -> download_episode -> build_episode -> host fallback -> yt-dlp -> naming
  -> completion path and state -> Sonarr import

STRM job / playback
  -> scheduler direct-file or proxy-URL mode
  -> StrmIdentity -> build_episode -> host fallback
  -> independent HTTP proxy transport / playlist rewriting
```

The update affects multiple entry points through shared helpers. A successful direct-link call does not validate queue state, proxy cookies, cancellation, or import paths.

## File-by-file boundary map

| Location | Responsibility | Upgrade requirement |
| --- | --- | --- |
| `apps/api/pyproject.toml`, `uv.lock` | Pin and resolved dependency graph | Exact candidate, targeted lock update, platform checks |
| `app/utils/aniworld_compat.py::prepare_aniworld_home` | Writable upstream initialization | Deliberate config directory before imports; no accidental ambient user configuration |
| `app/core/downloader/episode.py::build_episode` | URL/coordinate normalization and legacy/new model selection | Preserve AniWorld film URLs, s.to episode URLs, explicit site selection |
| `EpisodeCompat.available_languages` | Translate real upstream enum tuples into public labels | Test AniWorld config enums and separate s.to enums |
| `EpisodeCompat._get_provider_redirect_url` | Read raw dict or ProviderData wrapper; select language/host | Reject missing hosts and preserve requested language |
| `EpisodeCompat.get_direct_link` | Delegate to host registry and retries | Keep caller API stable; typed failures instead of guessing from strings |
| `app/core/downloader/extractors/voe.py` | Local HTTP/redirect/challenge/HTML parsing | Bound operations, preserve verified TLS, redact URL tokens, distinguish challenge from missing source |
| `app/hosts/bridge.py::resolve_via_aniworld` | Registry lookup then dynamic module fallback | Real installed callable checks; no silent broken imports |
| `app/hosts/{voe,filemoon,streamtape,vidmoly,doodstream,loadx,luluvdo,vidoza}.py` | Eight upstream-backed host wrappers | One-URL invocation remains valid |
| `app/hosts/gxplayer.py` and Megakino modules | Local/non-upstream paths | Preserve behavior; no provider expansion |
| `app/providers/sto/v2.py` | Existing BeautifulSoup button parser and language labels | Reusable for controlled s.to metadata transport; not a dead requirement to remove blindly |
| `app/providers/base.py`, `app/utils/title_resolver.py` | Catalog title/alias parsing and cache | These remain local; upgrading upstream does not replace catalog discovery |
| `app/providers/aniworld/specials.py` | Canonical/source special mapping | Preserve numbering semantics and existing regressions |
| `app/core/downloader/provider_resolution.py` | Language validation and ordered host fallback | Preserve configured order; do not retry absent hosts as network failures |
| `app/core/downloader/download.py`, `ytdlp.py` | Media download, cancellation, progress, final naming | Do not replace with upstream queue/download API |
| `app/core/scheduler.py` | Background jobs and direct/proxy STRM creation | Correct failure/completion state remains mandatory |
| `app/core/strm_proxy/resolver.py` | Identity to URL/host pair | Preserve return contract and cache identity |
| `app/api/strm.py` | Separate httpx transport, URL checks, HLS rewriting | Extractor cookies/headers do not automatically reach it |
| `app/api/qbittorrent/torrents.py`, `sync.py` | Client-visible state and output path | Preserve Sonarr polling/import semantics |
| `app/api/torznab/api.py`, `tvsearch.py`, `search_handlers.py` | Discovery/XML/season/ID behavior | Avoid expensive extraction for every fast season result |
| `tests/conftest.py`, VOE tests | Existing mocks and environment reset | Add separate real-package contracts; do not replace all useful mocks |
| Dockerfile, entrypoint, release workflow | Deployment and binary packaging | Non-root imports, native dependencies, frozen lock, resources |

The complete direct `aniworld` import locations and line numbers are captured in [import-inventory.json](evidence/import-inventory.json). Dynamic imports in `hosts/bridge.py` and host-wrapper module/function strings supplement that AST list.

## Stable facade contract

Callers currently need an episode built by `(link)` or `(site, slug, season, episode)`, language availability, and `get_direct_link(host, language)`. Maintain that surface while isolating upstream implementation details. Expose public language labels, not upstream enum objects. Preserve a clear distinction between catalog sites and video hosts.

An eventual local protocol can describe these needs without requiring the nonexistent generic upstream Episode type:

```python
class EpisodeSource(Protocol):
    @property
    def available_languages(self) -> list[str]: ...

    def get_direct_link(self, provider_name: str, language: str) -> str: ...
```

This is a design sketch, not implemented code. Include link/identity attributes only where current callers actually read them. Preserve compatibility aliases such as `language_name` if used. Avoid spreading `Any` or new upstream-private member access outside the adapter.

## Language and identity invariants

- German Dub, German Sub, English Sub, and English Dub remain semantically distinct.
- s.to's German Dub is not AniWorld's Japanese audio with German subtitles.
- Missing requested language is a deterministic failure, not permission to fall back to another language.
- Host fallback changes video host only; it must not change site, episode, language, or canonical mapping silently.
- Site aliases used for HTTP routing must not change persisted identity from `s.to` to a rotating domain.
- Preserve season zero / `filme/film-N` behavior for AniWorld and existing specials mapping.
- Synthetic Torznab identities must round-trip through qBittorrent payload parsing without changing site or language.

## Existing weaknesses relevant to the change

1. Generic `Episode` annotations do not describe either installed target. Replace when touching the boundary; avoid a broad annotation-only rewrite.
2. `provider_resolution._try_get_direct` classifies language errors by matching text. A changed upstream message can alter behavior. Translate upstream failures into existing local error types at the boundary.
3. The resolver returns a bare URL. A new upstream path that requires cookies, Referer, or User-Agent cannot be adopted as though that string captures the full request context. Either keep the verified URL-only path for this increment or introduce a bounded result carrying necessary context and update *all* consumers, including proxy and yt-dlp, in a separate clearly justified slice.
4. `_resolve_provider_redirect_url` takes `response.url` without an explicit status check. Error pages can become extractor input. Improve only with regression coverage preserving valid HTTP/JS redirect chains.
5. Local VOE redirect selection uses heuristic URL scanning and public-host filtering. Do not broaden it to arbitrary URL execution or remove host restrictions to make one sample pass.
6. Current logging can include full signed URLs and redirect tokens. Diagnostics should retain hostname, stage, HTTP status, content type, and classification; avoid adding raw body/cookie logging.
7. Catalog requests, niquests, requests, curl-cffi, httpx, and yt-dlp do not share session state by default. A successful browser action is not evidence every consumer can access the stream.

These are specific implementation considerations, not a mandate to fix unrelated architecture in this PR.

## API checks the next agent must preserve

Torznab: caps; title search; exact episode; fast season search; source/canonical special mapping; categories and external ID hints; language-specific result naming; synthetic download payload integrity.

qBittorrent: login behavior; add; info; sync polling; save/content path; progress and failure visibility; completed task identity; delete/cancel behavior without deleting unrelated files. Pause/resume must be characterized against the selected main baseline; do not import #119's changes accidentally.

STRM: `no`, `direct`, `proxy`, and combined modes as supported by config; direct URL expiration limitations; proxy token/auth behavior; HLS rewriting and range handling; cache identity includes site, slug, season, episode, language, and preferred host.
