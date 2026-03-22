# Release and CI

## Scripts and Tooling

- `scripts/local_build_release.sh` — local release automation.
- `scripts/local_build_release.ps1` — PowerShell equivalent.
- `scripts/setup-codex-overlay.sh` — agent overlay helper.
- `scripts/startup-script.sh` — example startup script.

## Build and Release

- Version source: `VERSION` file.
- `Makefile` provides `patch`, `minor`, `major` targets using `bump2version`.
- Release targets prompt before bumping when `PUSH=ask`, print the real
  post-bump version, and use one atomic `git push --follow-tags` step so
  branch and tag publication cannot diverge.
- Version bumps also update `docs/src/openapi.json` (`info.version`) and `docs/package.json` (`version`) for the docs API reference.
- Python distributions built via `uv run --with build python -m build`.
- PyInstaller builds use `anibridge.spec` and `hooks/hook-fake_useragent.py`.
- Releases publish artifacts and SHA256 checksums via GitHub Actions on tag push.
- GitHub release bodies are hybrid: Gemini-generated narrative notes are supplied
  via `body_path`, and GitHub's native generated release notes are appended for a
  deterministic merged-PR/contributor section.

## Docs Build (Cloudflare)

Cloudflare uses `npm ci` for docs builds. Because this repo uses `vitepress@2.0.0-alpha.*`, npm may treat it as not satisfying peer ranges unless peer checks are relaxed. We ship `docs/.npmrc` with `legacy-peer-deps=true` to make CI installs deterministic.

For Pull Request preview links in Cloudflare's native PR status comment, use
`npx wrangler versions upload` as the Cloudflare Builds deploy command and keep
`preview_urls = true` in `wrangler.toml`.

## Release Playbook

1. Run tests: `pytest`.
2. Update docs as needed.
3. Bump version: `make patch|minor|major`.
4. If you used `PUSH=false`, push the resulting commit and annotated tag
   together with `git push --atomic --follow-tags origin HEAD`.
5. `release-on-tag.yml` and `publish.yml` trigger from the pushed tag.
6. Verify the GitHub release has generated notes and uploaded artifacts.
7. Verify GHCR image tags published.
8. Deploy docs with `wrangler publish` after a successful build.

## CI/CD Workflows

- `tests.yml`: runs `uv sync --frozen` and executes pytest.
- `format-and-run.yml`: runs `ruff format app` and auto-commits formatting changes.
- `publish.yml`: builds and pushes GHCR images.
- `release-on-tag.yml`: builds Python dists and PyInstaller artifacts on
  `v*` tags; artifact upload waits for generated release notes so failed
  note generation cannot publish a partial release entry. Release uploads enable
  GitHub's generated release notes so the published body includes both the
  AI-authored summary and GitHub's deterministic Markdown changelog.
