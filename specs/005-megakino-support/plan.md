# Plan

1. Build dynamic domain resolution infrastructure for megakino that fetches the current domain.

Create domain resolution utility:

- Implement fetch_megakino_domain() function to fetch domain
- Add timeout (10-20s) and error handling
- Return domain string or None
- Follow existing network patterns (proxy, user agent, timeout)
- Add logging

Integrate into startup lifecycle:

- Call domain resolution during startup
- Store resolved domain.
- Implement fallback chain: Fetch → MEGAKINO_BASE_URL env var → default "megakino.lol"
- Handle failures gracefully with logging

Add configuration:

- Add MEGAKINO_BASE_URL env variable support with default value
- Add megakino entry to CATALOG_SITE_CONFIGS with base_url, default_languages, release_group
- Leave alphabet_html and alphabet_url empty/null (megakino does not have a alpabet page like s.to/aniworld)

2. Integrate megakino into catalog and title resolver systems with search-only functionality (no alphabet page browsing).

Add URL pattern recognition:

- Add megakino entry to HREF_PATTERNS in app/utils/title_resolver.py
- Create regex pattern to extract slugs from megakino URLs
- Focus on direct URL slug extraction only

Enable search-only mode:

- Update slug_from_query() to handle megakino differently: skip index lookup, return query as-is or validate URL
- Add site-specific logic for megakino to allow direct slug/URL input without cached index
- Update load_or_refresh_index() to gracefully handle empty/null alphabet configs for megakino
- Add code comments documenting search-only mode limitation

Update Torznab API:

- Add "megakino" to supported sites list
- Update _slug_from_query() to handle megakino parameter
- Ensure episode probing uses megakino's default_languages from config
- Update capabilities endpoint to list megakino as available

3. Add configuration, health monitoring, and documentation for megakino integration.

Update environment configuration:

- Add MEGAKINO_BASE_URL to .env.example with comment explaining auto-resolution
- Add example value (commented or empty)
- Update CATALOG_SITES to include "megakino"
- Document domain resolution behavior and search-only limitation

Add optional health check:

- Implement check_megakino_domain_validity() to test HTTP connectivity
- Add MEGAKINO_DOMAIN_CHECK_INTERVAL config flag (default: 0/disabled)
- If enabled, spawn background thread (similar to IP check pattern)
- On failure, attempt re-resolution and update config
- Add thread cleanup in shutdown handler

Update documentation:

- Add megakino to README.md supported sites list
- Document domain resolution mechanism
- Add troubleshooting section for domain failures
- Document search-only mode limitation
- Note default languages may need adjustment

<!-- For further information on how to implement the megakino integration, refer megakino-downloader.md -->