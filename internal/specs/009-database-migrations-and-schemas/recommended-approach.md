# Recommended Approach

## Decision

Adopt Alembic for schema migrations while keeping SQLModel as the ORM layer and SQLite as the database engine. Make the database persistent by removing container startup deletion and by running migrations on startup under a feature flag.

## Rationale

- SQLModel is built on SQLAlchemy, and Alembic is the standard migration tool for SQLAlchemy.
- Alembic supports SQLite batch mode, which is required for schema changes that rebuild tables.
- The change is low risk because it preserves existing data access code and only formalizes schema evolution.

## High-Level Changes

- Add Alembic to runtime dependencies.
- Add `alembic.ini` and migration scripts under `app/db/migrations`.
- Add a migration bootstrap that handles legacy databases without Alembic versioning.
- Remove in-code migration logic and replace it with versioned migrations.
- Remove Docker startup DB deletion and run migrations on startup when enabled.

## Migration Policy

- All schema changes must be captured in Alembic revisions.
- Migrations must be additive and safe for existing installations.
- SQLite batch mode is required for any operation that alters primary keys or drops columns.
