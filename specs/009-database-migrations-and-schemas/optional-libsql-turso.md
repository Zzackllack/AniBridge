# Optional libSQL/Turso Path

## Purpose

Offer a SQLite-compatible remote storage option for deployments that need replication or remote access while keeping the SQLModel and Alembic stack.

## Summary

libSQL (Turso) provides a SQLite-compatible database with remote replication options. SQLAlchemy can connect using a libSQL dialect, enabling most ORM operations and Alembic migrations to continue working.

## Tradeoffs

Pros:

- SQLite-compatible SQL and semantics.
- Optional remote replication and backups.
- No server-side schema redesign required.

Cons:

- Additional runtime dependency and connection URL handling.
- Some SQLite pragmas and behaviors may differ.
- Extra operational complexity for credentials and networking.

## Implementation Sketch

1. Add libSQL SQLAlchemy dialect dependency.
2. Introduce a `DATABASE_URL` override to support `sqlite+libsql://...`.
3. Keep Alembic migrations unchanged; use the same revision scripts.
4. Document credentials and replication endpoints for operators.

## Out of Scope

- Automatic data migration to libSQL/Turso.
- Multi-tenant or sharded storage.
