# Release and CI

## Scripts and Tooling

- `scripts/local_build_release.sh` — local release automation.
- `scripts/local_build_release.ps1` — PowerShell equivalent.
- `scripts/setup-codex-overlay.sh` — agent overlay helper.
- `scripts/startup-script.sh` — example startup script.

## Build and Release

- Version source: `VERSION` file.
- `Makefile` provides `patch`, `minor`, `major` targets using `bump2version`.
- Version bumps also update `docs/src/openapi.json` (`info.version`) and `docs/package.json` (`version`) for the docs API reference.
- Python distributions built via `uv run --with build python -m build`.
- PyInstaller builds use `anibridge.spec` and `hooks/hook-fake_useragent.py`.
- Releases publish artifacts and SHA256 checksums via GitHub Actions on tag push.

## Docs Build (Cloudflare)

Cloudflare uses `npm ci` for docs builds. Because this repo uses `vitepress@2.0.0-alpha.*`, npm may treat it as not satisfying peer ranges unless peer checks are relaxed. We ship `docs/.npmrc` with `legacy-peer-deps=true` to make CI installs deterministic.

For Pull Request preview links in Cloudflare's native PR status comment, use
`npx wrangler versions upload` as the Cloudflare Builds deploy command and keep
`preview_urls = true` in `wrangler.toml`.

## Release Playbook

1. Run tests: `pytest`.
2. Update docs as needed.
3. Bump version: `make patch|minor|major`.
4. Commit and push changes.
5. Tag release: `make tag` or `git tag -a vX.Y.Z`.
6. Push tags to trigger `release-on-tag.yml` and `publish.yml`.
7. Draft release notes including migrations/API/compliance notes.
8. Verify GHCR image tags published.
9. Deploy docs with `wrangler publish` after a successful build.

## CI/CD Workflows

- `tests.yml`: runs `uv sync --frozen` and executes pytest.
- `format-and-run.yml`: runs `ruff format app` and auto-commits formatting changes.
- `publish.yml`: builds and pushes GHCR images.
- `release-on-tag.yml`: builds Python dists and PyInstaller artifacts on `v*` tags.
