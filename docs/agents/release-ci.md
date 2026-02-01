# Release and CI

## Scripts and Tooling

- `scripts/local_build_release.sh` — local release automation.
- `scripts/local_build_release.ps1` — PowerShell equivalent.
- `scripts/setup-codex-overlay.sh` — agent overlay helper.
- `scripts/startup-script.sh` — example startup script.

## Build and Release

- Version source: `VERSION` file.
- `Makefile` provides `patch`, `minor`, `major` targets using `bump2version`.
- Python distributions built via `python -m build`.
- PyInstaller builds use `anibridge.spec` and `hooks/hook-fake_useragent.py`.
- Releases publish artifacts and SHA256 checksums via GitHub Actions on tag push.

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

- `tests.yml`: installs `requirements-dev.txt` and runs pytest.
- `format-and-run.yml`: runs `ruff format app` and auto-commits formatting changes.
- `publish.yml`: builds and pushes GHCR images.
- `release-on-tag.yml`: builds Python dists and PyInstaller artifacts on `v*` tags.
