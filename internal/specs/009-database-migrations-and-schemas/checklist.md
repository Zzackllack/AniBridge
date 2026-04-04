# Implementation Checklist

## Persistence

1. Remove SQLite deletion in `docker/entrypoint.sh`.
2. Ensure Docker volume mount persists `/data`.
3. Confirm `DATA_DIR` resolves to a writable path.

## Migrations

1. Add Alembic dependency and update requirements.
2. Add `alembic.ini` and migration environment config.
3. Create initial schema revision.
4. Create legacy `episodeavailability` migration revision.
5. Implement migration bootstrap logic for existing databases.
6. Run migrations on startup behind `DB_MIGRATE_ON_STARTUP`.

## Rollout

1. Start a container with a new empty volume and verify tables are created.
2. Start a container with an old DB file and verify migration runs.
3. Verify normal API behavior and job lifecycle after migration.
4. Add documentation for operators on how to persist and upgrade.
