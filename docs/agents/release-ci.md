# Release and CI

## Scripts and Tooling

- `scripts/local_build_release.sh` — local artifact build helper.
- `scripts/local_build_release.ps1` — PowerShell equivalent.
- `scripts/release/cut_release.py` — authoritative semver bump helper used by CI.
- `scripts/setup-codex-overlay.sh` — agent overlay helper.
- `scripts/startup-script.sh` — example startup script.

## Build and Release

- Version source: `VERSION` file.
- Releases are cut by the `Release / Cut Release` GitHub Actions workflow.
- `Makefile` release targets are wrappers around `gh workflow run`; they do not
  create release commits or tags locally.
- Real releases are allowed only from the current `main` tip; non-`main`
  branches may run dry-runs only.
- Version bumps also update `docs/src/openapi.json` (`info.version`) and `docs/package.json` (`version`) for the docs API reference.
- Python distributions built via `uv run --with build python -m build`.
- PyInstaller builds use `anibridge.spec` and `hooks/hook-fake_useragent.py`.
- Release refs are created in CI only after tests and package-build preflight
  pass.
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

1. Run tests: `pytest`.
2. Update docs as needed.
3. Dispatch `make patch`, `make minor`, or `make major` from a machine with
   authenticated `gh`, or run `Release / Cut Release` directly in GitHub.
4. For rehearsal on a feature branch, run `make release-dry-run
   RELEASE_TYPE=patch|minor|major`.
5. Verify the workflow creates the release commit, annotated tag, GitHub
   release assets, and versioned GHCR image tags.
6. Deploy docs with `wrangler publish` after a successful docs build.

## CI/CD Workflows

- `tests.yml`: runs `uv sync --frozen`, executes pytest, and uploads captured
  failure output for pull request feedback.
- `pr-test-feedback.yml`: posts or updates a pull request comment when
  `tests.yml` fails on a PR, including the pytest output in a collapsed Markdown
  details block, and removes the comment automatically once the test run passes.
- `codeowners-review.yml`: checks pull requests for malformed `CODEOWNERS`
  rules, invalid or unresolved owner references, and newly added or renamed
  paths that are covered only by the global fallback rule, then posts or
  refreshes a remediation comment on the PR.
- `format-and-run.yml`: runs `ruff format app` and auto-commits formatting changes.
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
  tags outside the CI release workflow.
