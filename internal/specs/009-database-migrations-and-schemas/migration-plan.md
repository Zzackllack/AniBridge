# Migration Plan

## Overview

This plan introduces Alembic as the migration system, replaces ad-hoc runtime migrations, and ensures the SQLite database is persistent across container restarts.

## Step-by-Step Plan

1. Add Alembic to Python dependencies and runtime requirements.
2. Add `alembic.ini` at the repository root with `script_location = app/db/migrations`.
3. Create `app/db/migrations/env.py` configured for SQLModel metadata and SQLite batch mode (`render_as_batch=True`).
4. Add an initial Alembic revision that creates the current tables (`job`, `episodeavailability`, `clienttask`).
5. Add a follow-up revision that migrates legacy `episodeavailability` tables missing the `site` column and primary key element.
6. Add migration bootstrap logic that stamps legacy databases to the initial revision and then upgrades to head.
7. Replace `create_db_and_tables()` with `apply_migrations()` in app startup; keep `create_db_and_tables()` as a compatibility wrapper for tests.
8. Add `DB_MIGRATE_ON_STARTUP` config and enable migrations in `app/core/lifespan.py` when the flag is true.
9. Remove database deletion from `docker/entrypoint.sh` and optionally run `alembic upgrade head` in the entrypoint when enabled.

## Migration File Layout

- `app/db/migrations/env.py` for Alembic environment configuration.
- `app/db/migrations/versions/` for revisions, ordered and versioned.
- `alembic.ini` at repo root.

## Versioning Rules

- Revision filenames use a timestamp prefix and a descriptive slug.
- Each migration must include both `upgrade()` and `downgrade()`.
- Migrations that alter tables in SQLite must use batch mode or table rebuild logic.

## Bootstrap Behavior for Existing Databases

- If `alembic_version` does not exist and tables are present, stamp the initial revision, then run migrations to head.
- If the database is empty, run migrations from base to head to create the schema.
- If the `episodeavailability` table lacks the `site` column, run the legacy migration revision.
