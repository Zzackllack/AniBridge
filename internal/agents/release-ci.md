# Release and CI

## Scripts and Tooling

- `scripts/local_build_release.sh` — local artifact build helper.
- `scripts/local_build_release.ps1` — PowerShell equivalent.
- `scripts/release/cut_release.py` — authoritative semver bump helper used by CI.

## Build and Release

- Version source: `VERSION` file.
- Releases are cut by the `Release / Cut Release` GitHub Actions workflow.
- `Makefile` release targets are wrappers around `gh workflow run`; they do not
  create release commits or tags locally.
- Real releases are allowed only from the current GitHub default-branch tip
  (currently `main`); other branches may run dry-runs only. The Makefile still
  defaults to `main`, so changing the repository default requires coordinated
  release-policy changes.
- Version bumps also update `docs/src/openapi.json` (`info.version`) and `docs/package.json` (`version`) for the docs API reference.
- Python distributions built via `uv run --with build python -m build`.
- PyInstaller builds use `apps/api/anibridge.spec` and `apps/api/hooks/hook-fake_useragent.py`.
- Release refs are created in CI only after tests and package-build preflight
  pass.
- The release workflow pushes the release commit and tag over SSH with a
  repository deploy key; it requires the Actions secrets `RELEASE_DEPLOY_KEY`
  and `RELEASE_SSH_KNOWN_HOSTS`, and that deploy key must be allowed in the
  branch ruleset bypass list for `main`.
- Gemini release notes are best-effort; the workflow falls back to GitHub's
  generated notes if Gemini is unavailable or fails.
- GitHub release publication is centralized in one job so assets and release
  notes are published atomically.

## Docs Build (Cloudflare)

Cloudflare uses `npm ci` for docs builds. Because this repo uses `vitepress@2.0.0-alpha.*`, npm may treat it as not satisfying peer ranges unless peer checks are relaxed. We ship `docs/.npmrc` with `legacy-peer-deps=true` to make CI installs deterministic.

For Pull Request preview links in Cloudflare's native PR status comment, use
`npx wrangler versions upload` as the Cloudflare Builds deploy command and keep
`preview_urls = true` in `wrangler.toml`.

## Release Playbook

1. Run tests: `cd apps/api && pytest`.
2. Update docs as needed.
3. Dispatch `make patch`, `make minor`, or `make major` from a machine with
   authenticated `gh`, or run `Release / Cut Release` directly in GitHub.
4. For rehearsal on a feature branch, run `make release-dry-run
   RELEASE_TYPE=patch|minor|major`.
5. Verify the workflow creates the release commit, annotated tag, GitHub
   release assets, and versioned GHCR image tags.
6. Deploy docs with `wrangler publish` after a successful docs build.

## CI/CD Workflows

- `tests.yml`: runs `cd apps/api && uv sync --frozen`, executes pytest, and uploads captured
  failure output for pull request feedback. It ignores `v*` release-tag pushes.
- `pr-test-feedback.yml`: posts or updates tool-specific pull request comments
  when `tests.yml` or `pylint-quality.yml` fails, includes captured output in a
  collapsed Markdown details block, and removes each comment once its check
  passes.
- `codeowners-review.yml`: blocks malformed `CODEOWNERS` rules and invalid or
  unresolved owner references. It separately posts an informational notice for
  external contributors who are not listed as recurring code owners; fallback
  ownership alone is not treated as a failure.
- `pylint-quality.yml`: enforces the pylint score gate on branch pushes and pull
  requests, captures failure output for PR feedback, and ignores `v*`
  release-tag pushes.
- `format-and-run.yml`: runs `cd apps/api && ruff format app tests` and auto-commits formatting
  changes on branch pushes and pull requests, but ignores `v*` release-tag
  pushes.
- `pr-title-conventional.yml`: validates pull request titles against the
  Conventional Commits schema, posts a short remediation comment on failing
  pull requests, and removes that comment automatically once the title is fixed
  so squash-merge titles and release notes stay consistent.
- `publish.yml`: builds and pushes continuous-delivery GHCR images from `main`
  only.
- `cut-release.yml`: authoritative release workflow that validates `main`,
  creates the release commit and tag in CI, builds release artifacts, publishes
  versioned GHCR images, and creates the GitHub release.
- `release-on-tag.yml`: guardrail workflow that rejects manual pushes of `v*`
  tags outside the CI release workflow while allowing tags created by the
  release commit shape `chore(release): cut vX.Y.Z`.

## v3 integration and preview images

`main` remains default/stable; `v3` is the protected next-major integration base.
Follow [the transition checklist](../releases/v3-transition.md) before changing
defaults, release policy or image channels. The catalog PR is ongoing private-pilot
work, not a release declaration.

`preview-images.yml` publishes separate API/worker GHCR preview packages for
same-repository PRs into `v3` and pushes to `v3`/`preview/**`, using native AMD64
and ARM64 runners. It checks the actual source commit and installed imports,
then tags combined manifests by full SHA plus a moving PR/branch alias. Forks
and Dependabot events cannot publish. Pin digests for deployments; this workflow
does not deploy or update stable images. Broader required tests remain a
transition checklist item.

## Catalog follow-up gate

`tests.yml` now runs independent frozen API/core/worker projects on branch pushes
and PRs into `main` and `v3`, without path filters. Core/worker jobs build and
import actual installed wheels. `Tests / Required Gate` always runs and requires
all projects to succeed. YAML/actionlint and local Linux checks do not establish
GitHub-hosted execution or protection enforcement. Native preview image builds,
registry publication and any required-check policy change need their own evidence
and authorization. The draft PR is unchanged.
