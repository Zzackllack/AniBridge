# Security and Legal

## Credential Handling

- Do not commit secrets; use environment variables and `.env` files excluded from git.
- `ANIBRIDGE_GITHUB_TOKEN` should be a GitHub PAT with read access.
- Optional qBittorrent authentication uses Starlette signed sessions and an
  independent random `QBIT_SESSION_SECRET`. Never log credentials or cookies.
  `QBIT_USERNAME`/`QBIT_PASSWORD` and the secret must be configured together;
  sessions expire in one hour. Logout clears the client's cookie; a copied
  cookie remains valid until expiry or credential/secret rotation. Login
  admission is 60 attempts/minute per process, with no retained user IPs.
  Credentialed login input is bounded before framework parsing: 16 KiB,
  five seconds and at most 1,024 ASGI receive frames, including empty frames.
  Normal URL-encoded and multipart forms retain the framework's parser.
  Session keys use PBKDF2-HMAC-SHA256 (600,000 rounds) once at startup,
  binding the random secret and username. The key-format change expires older
  authenticated cookies; clients must log in again. No password hash is stored.
  Browser mutations reject a mismatched Origin. Use HTTPS and secure cookies
  outside trusted private HTTP networks. This protects `/api/v2` only; it does
  not authorize public exposure of legacy downloader or other routers.

## Data Protection

The API uses upstream urllib3 for Requests and `urllib3_future` for AniWorld's
Niquests dependency. Use the repository's uv source-build configuration; the
fork's default wheel replaces the `urllib3` namespace despite upstream package
metadata. Runtime flags cannot undo that installation. Recreate an existing
environment when adopting isolation and verify the installed-package regression
on native images; do not infer imported code from lockfile versions alone.

Certifi must exclude `emSign ECC Root CA - G3` (GHSA-6q48-6c7w-9gw2).
The package floors and frozen locks enforce a patched bundle; rebuild images to
adopt it. The installed-wheel regression checks the actual loaded roots as well
as the dependency requirement. Updating source does not patch existing services.
Pylint also has a security floor for its stats-cache pickle advisory; the API
does not invoke the linter in production.

- Downloads stored locally; TTL cleanup recommended to avoid retention issues.
- Logs may contain URLs; redact before sharing.

## Security Policy

- Follow `SECURITY.md` for vulnerability reporting.

## Legal Considerations

- Legal docs live under `docs/src/`.
- `docs/src/legal/index.md` is the legal/compliance landing page.
- `docs/src/legal/legal-notice.md` is the main legal notice and boundary
  statement.
- `docs/src/legal/acceptable-use.md` describes unsupported and disallowed use
  patterns.
- `docs/src/legal/dmca.md` provides the project-facing DMCA contact route.
- `docs/src/legal/rights-holder-notice.md` routes repository-specific
  complaints.
- `docs/src/legal/contributor-ip.md` states contributor provenance
  expectations.
- In-app outbound proxying was removed; use external VPN routing for compliance.
