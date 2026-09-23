# Verified baseline and research evidence

## Snapshot identities

| Item | Recorded value |
| --- | --- |
| AniBridge branch base | `1c9b3b9396a0c9c5c55217323b52272e5acb87b2` |
| Remote main observed via GitHub | `1b0370915243f86c020c62bfc336aa0f46eda2c3` |
| Difference | Six commits ahead, only `apps/api/uv.lock` changed |
| Remote lock updates | Mako 1.3.10→1.3.12; AnyIO 4.12.1→4.14.2; SoupSieve 2.8.4→2.9 |
| AniBridge project version | 2.5.2 |
| Original upstream pin | 4.2.1 |
| Candidate upstream pin | 5.0.6 |
| Upstream release commit | `cfc9781a0dccb4b493a53d9a06b5685d1454f050` |
| Upstream release date | 2026-09-09 21:47:28 UTC |
| Python used | CPython 3.14.7 |
| uv used | 0.12.17, Homebrew |
| Research host | macOS / Apple Silicon |

The branch was created from the local checkout before research. No hidden rebase was performed. Implementation must refresh against remote main and regenerate its candidate lock there, preserving those newer unrelated dependency versions. The passing results below apply to the exact branch base, not the later remote lockfile.

## Experiment layout

Two tracked-source snapshots were exported outside the workspace under `/tmp/anibridge-upstream-spec-20260920/`. The baseline used the original frozen lock. The candidate changed only the temporary copy's dependency constraint to 5.0.6 and ran targeted lock resolution. Separate virtual environments were installed. No existing workspace virtualenv was updated.

`uv sync --frozen --no-install-project` succeeded in both environments. A later `uv sync --frozen --no-editable` also succeeded in both, establishing local project-install viability. This is not a wheel/sdist/PyInstaller matrix or a Docker build.

The candidate graph added only curl-cffi 0.16.3, Patchright 1.62.3, and pyee 13.0.1, removed authlib 1.6.12, and changed aniworld 4.2.1→5.0.6. See [dependency delta](evidence/dependency-delta.json).

## E1 — Existing tests

| Environment | Corrected run | Duration |
| --- | --- | --- |
| Baseline 4.2.1 | 145 passed, 1 warning | 9.68 seconds |
| Candidate 5.0.6 | 145 passed, 1 warning | 9.68 seconds |

The run used `python -m pytest -o addopts='' -q`, so repository default coverage flags were disabled for this comparison. It collected the complete configured test suite; no test-selection filter was used.

Evidence: [baseline output](evidence/baseline-pytest.txt), [candidate output](evidence/candidate-pytest.txt).

### Harness errors encountered and corrected

Initial runs had identical failures in both versions:

- `test_repo_root_defaults_anchor_local_data_paths`: research had set `DATA_DIR` globally, but this test explicitly expects default repository-relative paths. Remove global DATA_DIR/DOWNLOAD_DIR overrides when running the full suite inside isolated copies.
- `test_main_outputs_release_plan_json`: a plain git archive has no Git metadata, but the release helper runs Git. Temporary copies were initialized and fetched the already-existing base commit, then reset to it; no new commit was created.

After correcting the harness, both passed. These are not upstream regressions. Future contract harnesses should avoid reproducing these mistakes.

Both runs emitted a Starlette/httpx TestClient deprecation warning and an unclosed terminal-log ResourceWarning at interpreter exit. They are baseline issues; the upstream update did not introduce them. Do not expand this change to a framework migration.

### Important coverage limitation

`tests/conftest.py` disables refresh/network behavior, stubs `aniworld.parser`, resets app modules, and patches scheduling. VOE tests inject fake models/config/extractor modules into `sys.modules`. The 145-test result proves compatibility with those tests, not full integration with the installed package. Older conversations mentioned other counts on other snapshots; do not repeat those as current results.

## E2 — Real-package contract probes

The research imported the actual installed upstream package, configuration, models, and extractor registry, not replacement fake modules. It then seeded only synthetic provider data on real episode objects to avoid network dependence for language/redirect checks.

Observed for both 4.2.1 and 5.0.6:

- No generic `aniworld.models.Episode` export; the runtime uses `EpisodeCompat`.
- `AniworldEpisode(url=...)` and `SerienstreamEpisode(url=...)` constructed successfully.
- Required language maps and GLOBAL_SESSION/header exports exist.
- All eight configured upstream-backed extractor functions are present and callable with one positional URL.
- German language selection and redirect lookup agree with the local facade.

Synthetic plain-HLS HTML was not parsed by 4.2.1's `extract_voe_source_from_html` but was parsed by 5.0.6. That is a demonstrated parser improvement, not proof that #158 involved this encoding.

An initial harness mistakenly looked for AniWorld's Audio enum in its episode module. It actually lives in configuration; Serienstream has its own enum class. Corrected probes use each provider's real enum source. Keep this distinction in implementation tests.

Evidence: [baseline contract](evidence/baseline-contract.json), [candidate contract](evidence/candidate-contract.json). Import timings are one warm local observation, not a benchmark or memory assessment.

## E3 — Fresh live resolution checks

The probe called `build_episode`, inspected available languages, called `get_direct_link('VOE', 'German Dub')`, then fetched at most an initial 2048-byte response chunk to recognize an HLS playlist. No video segments were downloaded. Separate processes were used for each dependency environment.

| Example | 4.2.1 | 5.0.6 |
| --- | --- | --- |
| AniWorld One Piece S01E01, German Dub, VOE | resolved; HTTP 200 HLS | resolved; HTTP 200 HLS |
| Serienstream Avatar 2024 S02E01, German Dub, VOE | resolved; HTTP 200 HLS | resolved; HTTP 200 HLS |

Evidence: [baseline live](evidence/baseline-live.json), [candidate live](evidence/candidate-live.json).

The local redirect retry count was set to zero and redirect timeout to ten seconds for bounded research; upstream's own fallback can have separate defaults. No challenge appeared on these tested successful paths. The result is specific to this machine, time, network, provider state, and language.

## What remains unverified

- Actual challenge response on the reporter's failing IP.
- Complete Sonarr/Prowlarr request→queue→download→completed→import flow.
- Full media playback, audio correctness, file naming after download, subtitles, resume/cancel behavior against real clients.
- Megakino and alternate video hosts live functionality.
- AniWorld special/film numbering and all language variants with live media.
- Runtime in Linux amd64/arm64 containers; Docker daemon was unavailable.
- Browser installation, profile persistence, display requirements, concurrent browser use.
- Packaged single-file applications and their dynamically imported resources.
- Tests against the remote main lockfile and any later upstream release.

A future agent must preserve these limitations in the implementation PR and close each required gate with evidence, not infer them from successful playlist fetching.

## E4 — Dependency consistency and controlled transport test

`uv pip check` passed for both installed environments after non-editable project installation. Evidence: [baseline consistency](evidence/baseline-pip-check.txt), [candidate consistency](evidence/candidate-pip-check.txt).

A fake-session test against the installed 5.0.6 Serienstream helper confirmed that two simulated domain failures lead to an IP request with `verify=False`. A synthetic 403 response from that final request was returned rather than raised. No network request occurred. Evidence: [transport trace](evidence/serienstream-transport.json). Reproduction is included in the research document.
