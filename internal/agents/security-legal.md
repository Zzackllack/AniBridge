# Security and Legal

## Credential Handling

- Do not commit secrets; use environment variables and `.env` files excluded from git.
- `ANIBRIDGE_GITHUB_TOKEN` should be a GitHub PAT with read access.

## Data Protection

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
