# Validation plan and release gates

## Principle

Compare the same AniBridge source against original and candidate dependencies before changing integration logic. Then test each integration adjustment independently. Mark evidence as mocked, real-package/offline, live network, container, or real-client end-to-end.

The existing 145 tests and fresh playlist probes are a useful baseline, not release approval. The following tests are necessary because integration failures can be hidden by module replacement in `sys.modules`.

## G1 — Dependency and installation

- Confirm target tag and PyPI package identity; retain exact hashes in the handoff/lock.
- Resolve on current main without updating unrelated packages unnecessarily.
- `uv sync --locked` must agree with pyproject; `--frozen` alone deliberately skips freshness checking.
- Install the project non-editably and run `uv pip check` in the candidate environment.
- Validate with Docker's pinned uv version as well as local tooling.
- Build sdist/wheel and inspect expected application resources; run from the installed artifact outside the source directory.

Pass: no undeclared dependency conflict, no accidental extra upstream service started, and no reliance on the developer's existing virtualenv.

## G2 — Real-package offline contracts

Run each import/initialization scenario in a new subprocess with temporary data/config paths and no network. Replace only controlled transport responses or injected metadata, not entire upstream modules.

| Case | Expected assertion |
| --- | --- |
| Import models/config/registry | Required symbols load without CLI argument parsing or app server startup |
| Generic Episode absent | Chosen facade works without it |
| AniWorld episode and film URL | Correct identity, season zero behavior retained |
| Serienstream episode URL | Configured base URL preserved |
| All existing language labels | Real enum values map to the intended public label |
| Host missing for selected language | No wrong-language fallback or network retry |
| Eight extractor entry points | Present and callable through local wrappers |
| ProviderData dict versus wrapper | Both supported deliberately, no accidental assumptions |
| Upstream config path | Writes remain inside temporary/explicit directory |
| Read-only home/non-root | No global-home mutation required or uncontrolled writes |
| New plain-HLS parser fixture | 5.0.6 extracts expected synthetic URL |
| Request headers/cookies needed | Explicitly handled or unsupported with clear error |

Use controlled synthetic HTML for parser contracts. Prefer injected fetch responses so real parsing runs. If a test seeds a private cache, label it as a shape-only contract; it does not test parsing and must not be the only coverage.

## G3 — Transport and failure fixtures

Add cases for:

- HTTP redirect leaving Serienstream and then a VOE JavaScript redirect.
- HTTP 200 challenge document on the catalog redirect.
- HTTP 403/429/503 with and without recognizable challenge markup.
- HTTP 404/410 terminal source removal.
- Valid page with a challenge-related script but usable content (false-positive protection).
- Empty or changed provider markup with no challenge evidence.
- Redirect to private/local address rejected according to existing rules.
- Unresolvable host, timeout, and dropped connection.
- Configured STO_BASE_URL honored; no hard-coded raw-IP `verify=False` request.
- Repeated provider errors bounded; no unbounded futures, threads, or browser children.
- Logging omits query tokens, cookies, and full HTML.

Pass: clear failure classification, retry budget enforced, API/job remains usable after failure, and successful generation of a typed error does not count as a successful stream.

## G4 — Existing API and state regressions

Run the full suite after integration edits, with repository-required formatting/lint checks scoped appropriately. Preserve tests for:

- Torznab search, tvsearch, fast season behavior, specials and ID mapping.
- Synthetic magnet/payload round-trip and language-specific naming.
- qBittorrent add/info/sync states, output paths, errors, and deletion/cancellation.
- Download progress completion only after actual output exists.
- Direct/proxy STRM mode behavior, token authentication, HLS rewrite and URL validation.
- Megakino's existing local route without adopting unrelated upstream models.

Do not replace failing assertions with blanket mocks to accommodate a dependency upgrade. Investigate whether the expectation is a real contract or an obsolete assumption.

## G5 — Container and packaged application

Build Linux amd64 and arm64 images from the exact candidate commit. Use an isolated project name, fresh volumes, and no production endpoints/configuration. Do not deploy to the maintainer's infrastructure for these checks.

Check non-root startup, /health, writable data/config paths, package versions, native library loading, expected certificates, ffmpeg availability, and absence of unexpected browser/server processes. Check that a blocked provider terminates within the documented budget even when Chromium is absent.

Use a 4-GB memory limit for the integration smoke environment to catch obvious resource regressions; this is not the catalog bootstrap benchmark. Record memory/process counts around ordinary requests and failures. Do not infer container memory from one local import timing.

For PyInstaller, use the actual release command with hooks. Run the built program outside the source tree. Exercise dynamic extractor imports and resource loading. Validate Linux/macOS/Windows according to existing distribution support; if unavailable locally, require CI evidence or explicitly limit the release channel rather than marking it tested.

## G6 — Bounded live provider checks

Use one valid AniWorld episode and one s.to episode, including #158's example while available. Record date, package version, network context (without public IP), site, language, host, stage reached, HTTP status, and playlist validity. Avoid recording signed direct links or tokens.

Probe supported alternate language and host only when present. Failure because the host is absent is not an extractor regression. Do not crawl whole catalogs for this step. Do not repeatedly hit a challenged endpoint to obtain a green result. If content changes, select another representative example and record why.

Research examples:

- `https://aniworld.to/anime/stream/one-piece/staffel-1/episode-1`
- `https://serienstream.to/serie/avatar-herr-der-elemente-2024/staffel-2/episode-1`

Use bounded playlist fetching; media download needs a separately chosen lawful test item for the complete-flow gate. Do not assume title availability or rights from a URL in an issue.

## G7 — Complete *arr integration (required release evidence)

Set up isolated Sonarr/Prowlarr and AniBridge instances using the development Compose configuration as a starting point. Verify the actual services/paths in that file before running it; agent documentation contains older filenames. Use temporary config/download/library volumes and explicit API keys. Do not expose the test stack publicly.

1. Confirm health and version/package evidence from the running container.
2. Configure Torznab indexer and qBittorrent-compatible download client through the real client UI/API. Confirm their connection tests succeed.
3. Select a permitted small media fixture/example with known season, episode, audio, and expected output naming. If no permitted live item is available, run the protocol/download lifecycle with a controlled local fixture and record the live-provider gap separately.
4. Search through the real client, select the expected result, and verify the identity/language sent in the add request.
5. Observe queued/running/progress/error/completed transitions through real qBittorrent polling.
6. Verify the file exists at the reported content/save path and is visible through the shared mount to Sonarr. Verify naming, container format, and intended audio track.
7. Verify Sonarr import and episode association; absence of an error alone is not an import assertion.
8. Repeat the relevant STRM workflow separately. Verify the file content/URL and playback through the supported consumer. Do not assume Sonarr imports `.strm` identically to media files; record actual client behavior.
9. Exercise cancellation and a controlled failure; ensure no false completion, orphan worker, or unintended file deletion.
10. Restart the test service and confirm its expected persisted job/config behavior remains intact.

Evidence table must name the client versions, image/commit, fixture, exact stage reached, and any failed or skipped step. Screenshots or sanitized API responses can substantiate client state. This research did not perform G7.

## Exit decision

Ship only when required gates have concrete results and transport/browser behavior matches the documented contract. Do not merge merely because the old mocked suite remains green. If #158 remains network-dependent and unreproduced, leave it open with an accurate note; the compatibility update can be valuable without claiming to solve it.
