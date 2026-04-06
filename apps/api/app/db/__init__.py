"""Database package: SQLModel models, engine, and CRUD helpers.

This package contains the SQLite/SQLModel data models and related utilities
that used to live in `app/models.py`. Functionality and public API are preserved;
imports should now use `from app.db import ...`.
"""

from . import models as _models

__all__ = [name for name in dir(_models) if not name.startswith("_")]
globals().update({name: getattr(_models, name) for name in __all__})
