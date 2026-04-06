# Assumptions and Defaults

## Assumptions

- SQLite remains the primary database engine for this project.
- The existing SQLModel models remain the source of truth for schema intent.
- Deployments can mount a persistent volume at `/data` in Docker.

## Defaults

- Database file path: `DATA_DIR/anibridge_jobs.db`.
- `DB_MIGRATE_ON_STARTUP`: enabled by default in Docker environments.
- Alembic is the migration system and is required at runtime.

## Notes

- This spec does not introduce a new `DATABASE_URL` override. If needed, it can be added later without breaking the Alembic setup.
