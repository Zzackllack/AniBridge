# Quickstart – Dual Catalogue s.to Support

1. **Update configuration**
   - Set `CATALOG_SITES=aniworld,s.to` (default order) or adjust priority as needed.
   - Optional: define `SITE_BASE_URL_ANIWORLD` / `SITE_BASE_URL_STO` when using mirrors.
   - Ensure `PREFERRED_LANGUAGES_ANIWORLD` and `PREFERRED_LANGUAGES_STO` reflect desired language ordering.

2. **Install dependencies**
   - Existing stack remains FastAPI/Python/SQLite.
   - If new Python packages are required (e.g., for HTTP resilience), add them to `requirements.runtime.txt` and regenerate lock files.
   - Re-run `pip install -r requirements-dev.txt` for development environments.

3. **Run migrations / data prep**
   - Execute a lightweight migration adding `source_site` columns to job/availability tables (SQLModel migration script TBD).
   - Purge or backfill caches to ensure the new per-site keys populate cleanly.

4. **Start AniBridge**
   - `python -m app.main` (development) or use Docker Compose as usual.
   - Confirm `/health` shows both catalogues enabled under diagnostics.

5. **Validate behaviour**
   - Run automated tests: `pytest tests/api/test_torznab.py tests/api/test_qbittorrent_sync.py`.
   - Manually trigger a Torznab search for an s.to-exclusive series and confirm results include `<anibridge:sourceSite>sto`.
   - Verify qBittorrent `/sync/maindata` payload returns `anibridge_source_site` for active torrents.
