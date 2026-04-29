"""Database package: SQLModel models, engine, and CRUD helpers.

This package contains the SQLite/SQLModel data models and related utilities
that used to live in `app/models.py`. Functionality and public API are preserved;
imports should now use `from app.db import ...`.
Runtime export is intentionally dynamic; see `__init__.pyi` for Pylance food.
"""

from . import models as _models

# TODO: Clean up this this runtime facade and static type hinting
# It's a bit hacky but never caused any issues
# we should replace the dynamic globals().update(...) with a normal star import
# or eventually explicitly define what this package exports
__all__ = [name for name in dir(_models) if not name.startswith("_")]
globals().update({name: getattr(_models, name) for name in __all__})
