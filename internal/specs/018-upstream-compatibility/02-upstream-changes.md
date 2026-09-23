# Upstream release, dependency, and behavior changes

## Provenance

Research target: published package `aniworld==5.0.6`, Git tag `v.5.0.6`, commit `cfc9781a0dccb4b493a53d9a06b5685d1454f050`. GitHub release and PyPI metadata agree on the version; PyPI declares Python >=3.11. Package artifact hashes are in [upstream-artifacts.json](evidence/upstream-artifacts.json).

The comparison from `v.4.2.1` to `v.5.0.6` contains 311 commits. The source diff spans 203 files, 49,911 insertions and 8,198 deletions. These figures describe upstream breadth, not the amount AniBridge needs to adopt. Its default development branch is named `models`; do not mistake branch head for the released artifact.

Context7 did not return an AniWorld-Downloader documentation entry. Direct tagged source, published metadata, and local installed-package probes were used instead. Context7 did provide uv documentation for the environment/lock workflow.

## Dependency impact

| Package | Original lock | Candidate lock | Meaning |
| --- | --- | --- | --- |
| aniworld | 4.2.1 | 5.0.6 | Target dependency |
| authlib | 1.6.12 | absent | Upstream SSO becomes optional; AniBridge does not need upstream SSO |
| curl-cffi | absent | 0.16.3 | Native HTTP transport used by VOE fallback |
| patchright | absent | 1.62.3 | Browser automation package/driver |
| pyee | absent | 13.0.1 | Transitive browser dependency |

The newer package also continues to include general application dependencies such as Flask, Flask-WTF, and Waitress in its base distribution. Installing them does not mean AniBridge should start upstream's web server. Do not install `[all]`, `[discord]`, or `[sso]` extras for this migration.

The resolved lock contains curl-cffi and Patchright wheels for macOS ARM64 and Linux x86_64/aarch64, among other platforms. Wheel availability is not a tested image build or browser runtime. Native libraries, browser binaries, certificates, executable permissions, and bundle resources remain packaging concerns.

## Models and language contracts

The site-specific model exports exist in both tested versions. Generic Episode is absent in both, so upgrading does not newly remove the runtime path actually exercised today. TYPE_CHECKING imports referencing that generic class are misleading type documentation and should become a local protocol when touching the boundary.

AniWorld's language enums/maps live in config. Serienstream defines separate Audio/Subtitles enums in its episode module. Comparing values can be necessary across those enum types; identity equality across modules is not reliable. AniBridge already handles tuple value comparison in its compatibility facade. Test real enum objects rather than creating matching-looking mock enums only.

Upstream 5.0.6 supports additional catalog families and browser/download functionality. They are out of scope: exposing them requires URL recognition, Torznab categories, identifier matching, language/episode mapping, and lifecycle evidence, not just an upstream class import.

## Serienstream transport: new behavior that is reached

`models/s_to/http.py` is new since 4.2.1. It owns module-global active-host state and tries `serienstream.to`, then `serienstream.cx`, then a hard-coded IP with a Host header and TLS verification disabled. It suppresses InsecureRequestWarning. Its final IP response is returned without the same explicit `raise_for_status` used for normal hosts.

`SerienstreamEpisode._html` calls this helper. AniBridge reaches `_html` when evaluating provider metadata, even though it does not use upstream's final `provider_url` property. Therefore this part of upstream behavior does affect a pin-only upgrade.

The helper chooses its own domains rather than receiving AniBridge's STO_BASE_URL policy. Redirect maps are built using upstream's active host. A base-URL override may therefore build the requested episode URL locally while upstream fetches or returns redirects on a different host. This must be explicitly tested and controlled, not described as an innocuous implementation detail.

## Serienstream browser flow: behavior currently bypassed

Upstream's `provider_url` first tries its own HTTP helper. If the request remains on the catalog host, it invokes `solve_sto_modal` with episode URL, selected host, selected language, and redirect URL. It checks that the result is a nonempty external URL.

AniBridge instead reads `provider_data`, selects a redirect token, and passes it through its local `_get_direct_link_with_retries`. Consequently, simply updating the package does not switch AniBridge onto this episode-level browser flow. Do not replace this path with `.stream_url` without accounting for selected language/provider mutation, concurrent use, browser startup, timeouts, and download headers.

## VOE extraction: improvements partially reached

5.0.6 supports encoded JSON payloads, an additional encoded variable form, and a plain HLS field in the HTML parser. Its network extraction path prefers curl-cffi, follows embedded redirects, has challenge handling, and avoids retrying permanent HTTP 404/410 failures.

AniBridge's local s.to fast path calls the upstream HTML parser but fetches pages with `requests`. Its fallback host wrapper calls upstream's network extractor, so transport improvements can be reached there. Different sessions/transports can see different challenge results. Browser cookies installed in GLOBAL_SESSION do not automatically propagate into plain requests, curl-cffi, httpx STRM proxy requests, or yt-dlp.

Issue #158 was not shown to be an encoding regression. The raw failing page remains unknown, and old/new dependencies both resolve the sample on this research connection.

## Browser, configuration, and import side effects

Importing upstream config invokes `initialize_app_env`: it resolves ANIWORLD_INSTALL_FOLDER (or a pointer in the default .env), merges upstream defaults into an on-disk .env, and loads settings. This is not a pure import. Research explicitly supplied temporary configuration directories.

Upstream config also defines a shared niquests session with a Cloudflare DoH resolver and headers. This is a different resolver/transport from some AniBridge requests and should be included when interpreting network-dependent results. Importing the extractor registry enumerates/imports modules eagerly; importing models can transitively import extractors and browser helpers. Symbol probes must happen in fresh processes to expose missing dependencies and side effects.

Patchright being importable does not install Chromium. Upstream's own Dockerfile includes browser/display setup and Xvfb; AniBridge's Dockerfile does not. Some upstream challenge timeouts default to minutes and are separate from AniBridge's redirect request timeout. A Python thread wait timeout cannot terminate a browser or network call already executing elsewhere.

Upstream's profile directory can be controlled by ANIWORLD_BROWSER_PROFILE and otherwise derives from its config directory. Docker and desktop profile behavior differs. This research did not run a browser or measure its memory usage. Interactive verification and browser persistence remain a separately scoped feature.

## Packaging and operational concerns

AniBridge's Docker build uses uv 0.10.0, while this research used 0.12.17. Validate the candidate lock with the build's uv version before release; do not silently upgrade unrelated tooling to conceal incompatibilities. The local no-editable install passed, but the image has not been built here.

Release binaries use dynamic imports and upstream package data. The workflow actually invokes PyInstaller with `--additional-hooks-dir hooks --onefile app/main.py`; do not assume editing only `anibridge.spec` affects that workflow. Validate extractor discovery, upstream .env resources, curl-cffi libraries, and driver resources in the built artifact.

`ffmpeg-python` is a Python wrapper, not an ffmpeg executable. AniBridge's download path uses yt-dlp and requests ffmpeg behavior, while the inspected Dockerfile does not explicitly install ffmpeg. This is an existing packaging concern to verify in the full download gate, not a demonstrated upgrade regression.
