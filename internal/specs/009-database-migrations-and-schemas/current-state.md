# Current State Analysis

## Database Initialization Flow

- Models and SQLAlchemy engine are defined in `app/db/models.py` using SQLModel.
- `DATABASE_URL` is derived from `DATA_DIR/anibridge_jobs.db`.
- Startup uses `app/core/lifespan.py` to call `create_db_and_tables()` and then clean dangling jobs.

## Schema Definition Location

- SQLModel models live in `app/db/models.py`.
- The module uses a private SQLAlchemy registry (`ModelBase`) to avoid duplicate model warnings in tests.

## Ephemeral Behavior in Docker

- `docker/entrypoint.sh` deletes `anibridge_jobs.db` (and `-wal`, `-shm`) on every container start.
- This makes the SQLite database ephemeral even when a volume is mounted.

## Ad-hoc Migration Logic

- `_migrate_episode_availability_table()` in `app/db/models.py` performs an in-place SQLite migration.
- It rebuilds `episodeavailability` to add the `site` column to the primary key.
- This is a one-off migration embedded in runtime code, not versioned.

## Testing Behavior

- Tests set `DATA_DIR` and `DOWNLOAD_DIR` to temporary directories in `tests/conftest.py`.
- Tests call `create_db_and_tables()` to initialize schema for each test session.
