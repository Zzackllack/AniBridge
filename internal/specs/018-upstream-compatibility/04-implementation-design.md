# Proposed implementation design

This is the prescribed direction for the implementation agent. It separates a dependency update from behavior changes that require their own evidence. No production implementation was made during research.

## 1. Start from a fresh base and retain a comparison environment

Refresh the implementation branch against current main before code changes. Re-run the baseline with its current frozen lock. The research branch began six dependency-only commits behind main; do not overwrite newer lock versions with the temporary candidate lock from this study.

Change only the aniworld constraint to `==5.0.6`, then use targeted lock resolution. Inspect every removed, added, and changed package. No `uv lock --upgrade` across the whole environment. Install the project normally and run dependency consistency checks.

## 2. Establish a narrow integration module

Keep upstream imports in a small compatibility boundary and the host bridge. Existing `EpisodeCompat` is an acceptable starting point. Do not create a generalized plugin framework or replace all catalog code.

Use a local EpisodeSource protocol for caller typing. Preserve `build_episode` and its caller-facing behavior so API/scheduler changes are minimal. Separate:

- episode identity and local language labels;
- fetching/parsing source metadata;
- selecting a host redirect;
- extracting a direct URL;
- consuming that URL through download or proxy.

Do not use upstream's `.download()` or web queue. AniBridge's yt-dlp callbacks, naming, job state, and STRM output remain authoritative.

## 3. Isolate s.to metadata transport

### Required behavior

A pin-only upgrade must not silently introduce unverified-TLS IP fallback or ignore STO_BASE_URL. Default requests must use HTTPS verification and the operator-configured catalog origin. Host changes need an explicit policy. Failures must preserve the difference between missing content, unavailable language/host, and blocked access.

### Preferred contained implementation if upstream still lacks transport injection

Reuse the existing local `providers/sto/v2.py::parse_episode_providers` with AniBridge's bounded verified HTTP client for the episode metadata needed by this service. Implement a small s.to source facade rather than calling the newer upstream metadata fetch path:

1. Build the episode URL with the existing site config and URL builder.
2. Fetch once using the controlled local transport, with an explicit timeout and HTTP status handling.
3. Recognize challenge/error documents before interpreting an empty host map as unavailable content.
4. Parse existing provider buttons into host → language-ID → redirect URL using the existing BeautifulSoup parser; retain `urljoin` behavior and semantic labels.
5. Expose the same public language/host selection behavior used by EpisodeCompat.
6. Resolve the selected redirect through the shared local host-resolution path, continuing to use upstream host extractors where their behavior meets the no-browser/timeout policy.

This avoids global monkeypatching, a forked upstream package, and a new duplicate parser. It also avoids reaching `sto_get` for metadata. Do not fetch unnecessary upstream Series/Season properties merely to construct an episode. Verify HTML parsing with representative synthetic fixtures and the live sample.

This recommendation is source-grounded but not implemented or benchmarked. If current upstream adds an injectable, verified transport before implementation, prefer that and update this decision. Do not reach into mangled private caches in production; the research probe seeded them only to isolate a contract test.

### Do not do these things

- Assign upstream module globals per request; concurrent jobs could route through each other's configuration.
- Remove TLS checks or allow all redirect destinations to force a successful test.
- Add an automatic round-robin of arbitrary mirrors to bypass a provider failure.
- Treat every empty parse as a confirmed challenge; absence and parsing changes are distinct.

## 4. Upstream configuration directory

Initialize before any import that transitively loads `aniworld.config`. Prefer the supported ANIWORLD_INSTALL_FOLDER setting, defaulting to an isolated path under AniBridge DATA_DIR if not explicitly configured. Preserve an explicit operator value; validate writability and report a clear failure.

The existing `prepare_aniworld_home` mutates process HOME and can reuse an unrelated user's upstream .env. Replace or narrow that behavior only with tests for default, explicit override, read-only home, and non-root containers. Do not copy private ambient settings into a published fixture. Decide and document migration for users who previously configured upstream under HOME; do not silently discard their explicit configuration.

If exposing/documenting ANIWORLD_INSTALL_FOLDER as an AniBridge-supported setting, update `.env.example`, configuration guidance, and Compose forwarding where appropriate. This research does not change environment defaults.

## 5. Bound host resolution and handle challenges

Define local typed outcomes at the integration boundary, preferably extending existing errors:

- requested language unavailable;
- requested host absent;
- provider access requires verification;
- temporary transport failure;
- source unavailable (e.g. confirmed 404/410);
- unsupported or unrecognized response.

Do not map every 403/429 to a CAPTCHA; retain HTTP status and stage. HTML challenge markers plus context can support classification, but must not classify normal episode pages containing challenge-related assets as blocked automatically. Include positive and negative fixtures.

For this increment, a challenge must return a bounded actionable error. It must not invoke an unprovisioned interactive browser. Upstream VOE's callable includes a browser path, so merely retaining `host.resolve()` and saying browsers are out of scope does not enforce this requirement.

A concrete option is to keep the local HTTP/HTML resolver as the controlled VOE path, using upstream's improved pure HTML decoder and a bounded verified transport, and avoid the network extractor when it would start browser solving. Keep redirect/source fixtures for both normal VOE JSON and JavaScript redirect responses. Do not copy upstream's entire browser implementation. Browser-assisted retry remains a later feature.

Apply retry policy once per operation where feasible; avoid multiplying local retries by upstream retries. A timeout waiting for a thread does not cancel the underlying operation. Network calls need their own timeouts; if introducing subprocess isolation for unavoidable blocking code, track process lifetime and cleanup explicitly. Do not add daemon-thread retries that accumulate abandoned work.

A source missing on one host may allow the next host. A catalog-level challenge should not trigger eight identical attempts against the same gate. Preserve the requested language throughout.

## 6. Request context and outputs

Do not change the URL-only return contract unless evidence shows that new required request headers/cookies cannot be preserved otherwise. If necessary, introduce a small immutable resolved-source object carrying URL, host, and narrowly scoped required headers/session reference. That is a separate implementation slice with updates to yt-dlp, quality probing, and STRM proxy consumers. Never pass browser cookies indiscriminately to a different host.

No resolved stream URL should enter the catalog as a durable identity. Keep caching/expiration behavior explicit. Direct STRM URLs can expire; proxy mode resolves again under existing semantics. Do not declare playback fixed after only validating the first HLS response.

## 7. Packaging strategy

Keep the default image usable without a browser. The upgrade may still contain browser packages because upstream requires them; don't remove mandatory Python dependencies. Do not install/download Chromium on startup. Verify non-browser extraction and imports on Linux amd64/arm64.

If an unavoidable path requires browser execution, stop calling this a narrow dependency bump and split browser provisioning into a separate specification/PR. That work includes system libraries, display/headless mode, memory/process limits, persistent profile permissions, authenticated UI access, restart behavior, and IP/session consistency.

Confirm ffmpeg availability for actual media download. Where an existing packaging gap blocks the release gate, report it explicitly and make a focused companion fix only if necessary; do not conceal it with host-installed tools.

## 8. Changes that are allowed only with evidence

Removing legacy generic-Episode construction can simplify the facade because neither tested pin exports it, but tests may currently rely on that branch. First replace fake legacy coverage with real-package equivalent coverage. Removing it is optional; it is not needed to justify the version bump.

Dropping custom fallback logic is allowed only after an equivalent normal, error, timeout, and challenge case passes through the replacement. Do not assume newer upstream always behaves better.

Adding support for new upstream hosts/catalogs is excluded. The API contract surface is larger than extractor discovery.
