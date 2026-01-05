# Plan

## Task: 1

Build dynamic domain resolution infrastructure for megakino that fetches the current domain.

Create domain resolution utility:

- Create new module app/utils/domain_resolver.py
- Implement fetch_megakino_domain() function to fetch domain
- Add timeout (10-20s) and error handling
- Return domain string or None
- Follow existing network patterns (requests library, proxy support, user agent, timeout)
- Add structured logging for success and failures

Integrate into startup:

- Call domain resolution during startup
- Store resolved domain.
- Implement fallback chain: Fetch → MEGAKINO_BASE_URL env var → default "megakino.lol"
- Log which source was used (resolved/fallback/default)
- Handle failures gracefully with warnings, don't block startup

Add configuration:

- Add MEGAKINO_BASE_URL env variable support with default value
- Add megakino entry to CATALOG_SITE_CONFIGS with base_url (using getter),alphabet_html=None, alphabet_url=None, default_languages=["Deutsch", "German Dub"], release_group="Megakino"
- Leave alphabet_html and alphabet_url empty/null (megakino does not have a alpabet page like s.to/aniworld)

---

## Task: 2

Integrate megakino into catalog and title resolver systems with search-only functionality (no alphabet page browsing).

Add URL pattern recognition:

- Add megakino entry to HREF_PATTERNS in app/utils/title_resolver.py: `re.compile(r"/serials/\d+-([^./?#]+)")`
- Update _extract_slug() to handle megakino URLs with new pattern
- Add docstring note explaining megakino URL format (/serials/<id>-<slug>.html) differs from other sites
- Validate extraction works for example: `/serials/5877-stranger-things-5-stafffel.html` → `stranger-things-5-stafffel`

Handle missing alphabet index:

- Update load_or_refresh_index() to detect when both alphabet_html and
alphabet_url are None
- Skip HTTP fetch and file loading, return empty dict immediately with info log
about search-only mode
- Update slug_from_query() to handle empty indexes: for megakino, treat query as
potential slug and validate format (alphanumeric-with-hyphens)
- Add docstring explaining direct URL mode requirement
- Ensure _should_refresh() doesn't trigger for sites with no alphabet sources

Update Torznab API:

- Add "megakino" to supported sites list
- Ensure _slug_from_query() delegates properly to title_resolver for megakino
- Confirm episode probing loop uses megakino's default_languages from
CATALOG_SITE_CONFIGS
- Update capabilities endpoint XML to include "megakino" in supported sites
- No changes needed to episode-level functions (site-agnostic)

---

## Task: 3

Add configuration, health monitoring, and documentation for megakino integration.

Update environment configuration:

- Add MEGAKINO_BASE_URL to .env.example with comment explaining auto-resolution
- Add example value (commented or empty)
- Update CATALOG_SITES to include "megakino"
- Document domain resolution behavior and search-only limitation

Add optional health check:

- Implement check_megakino_domain_validity() to test HTTP connectivity
- Add MEGAKINO_DOMAIN_CHECK_INTERVAL config flag (default: 100 minutes, 0 to disable)
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