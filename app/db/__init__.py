"""Database package: SQLModel models, engine, and CRUD helpers.

This package contains the SQLite/SQLModel data models and related utilities.
Database schema is now managed by Alembic migrations.

Key modules:
    - base: ModelBase class for all table models
    - session: Database engine and session management
    - models: Table models (Job, EpisodeAvailability, ClientTask) and CRUD functions
    - migrations: Alembic migration utilities for automatic schema management

Imports from app.db.models are re-exported for backwards compatibility.
"""

from .base import ModelBase
from .session import engine, get_session, dispose_engine, DATABASE_URL
from .migrations import run_migrations, get_current_revision, check_migrations_status
from .models import *  # re-export full surface for backwards compatibility

__all__ = [
    "ModelBase",
    "engine", 
    "get_session", 
    "dispose_engine",
    "DATABASE_URL",
    "run_migrations",
    "get_current_revision",
    "check_migrations_status",
] + [name for name in dir() if not name.startswith("_") and name not in ["base", "session", "models", "migrations"]]
