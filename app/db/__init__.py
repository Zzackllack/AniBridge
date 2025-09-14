"""Database package: SQLModel models, engine, and CRUD helpers.

This package contains the SQLite/SQLModel data models and related utilities
that used to live in `app/models.py`. Functionality and public API are preserved;
imports should now use `from app.db import ...`.
"""

from .models import *  # re-export full surface for backwards compatibility

__all__ = [name for name in globals() if not name.startswith("_")]
