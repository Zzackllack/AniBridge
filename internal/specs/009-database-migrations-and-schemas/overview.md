# Database Migrations and Schema Strategy Overview

## Goal

Move from a transient, startup-created SQLite schema to a persistent, versioned schema with repeatable migrations, while preserving the current SQLModel-based data access layer.

## Executive Summary

The repository already uses SQLModel (SQLAlchemy under the hood) and defines its schema in `app/db/models.py`. The most compatible and low-risk migration system for this stack is Alembic. Alembic is the standard migration tool for SQLAlchemy and supports SQLite batch mode, which is required for ALTER TABLE changes that rebuild tables.

Recommended path:

- Keep SQLite, but make persistence explicit via `DATA_DIR` and remove the container start-up deletion of the database file.
- Introduce Alembic migrations with SQLite batch mode (`render_as_batch=True`).
- Replace the ad-hoc in-code migration logic with formal Alembic revisions.
- Run migrations on startup under a guard flag (`DB_MIGRATE_ON_STARTUP`).

## Deliverables in This Spec Set

- Current state analysis with code references.
- Options comparison for migration tooling.
- Recommended approach and rationale.
- Implementation plan with ordered steps.
- Persistence and Docker changes.
- Migration and rollout checklist.
- Optional libSQL/Turso path.
- Explicit assumptions.

## Scope

- SQLite remains the primary database engine.
- No migration to external server databases (Postgres/MySQL) is proposed.
- Optional consideration: libSQL/Turso for SQLite-compatible remote storage.
