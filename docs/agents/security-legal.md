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
- `docs/src/legal.md` is the main legal notice and boundary statement.
- `docs/src/acceptable-use.md` describes unsupported and disallowed use
  patterns.
- `docs/src/rights-holder-notice.md` routes repository-specific complaints.
- `docs/src/contributor-ip.md` states contributor provenance expectations.
- In-app outbound proxying was removed; use external VPN routing for compliance.
