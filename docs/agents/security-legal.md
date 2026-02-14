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

- `LEGAL.md` documents jurisdictional risks and usage restrictions.
- In-app outbound proxying was removed; use external VPN routing for compliance.
