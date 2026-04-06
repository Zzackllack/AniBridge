# Persistence and Docker Changes

## Persistence Strategy

- Keep SQLite as a file-based database.
- Store the database at `DATA_DIR/anibridge_jobs.db`.
- Ensure `DATA_DIR` is a persistent mount in Docker deployments.

## Docker Entry Point Changes

- Remove deletion of the SQLite database file on container startup.
- Optionally run `alembic upgrade head` before launching the app when `DB_MIGRATE_ON_STARTUP` is enabled.

## Docker Compose Example

- Use a persistent volume mapping for `/data`.
- Keep `DATA_DIR=/data` to align with defaults.

## Environment Variables

- `DATA_DIR`: Path where SQLite database lives.
- `DB_MIGRATE_ON_STARTUP`: When true, migrations run automatically during startup.

## Operational Notes

- Ensure the container user has write access to `DATA_DIR`.
- For backup, snapshot the SQLite file and WAL files together if WAL mode is in use.
