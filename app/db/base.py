"""Base SQLModel class and metadata for all database models.

This module provides the base class that all SQLModel table models should inherit from.
It uses a private registry to avoid global state issues during testing.

The metadata from this base class is used by Alembic for automatic migration generation.
"""

from sqlmodel import SQLModel
from sqlalchemy.orm import registry as sa_registry

# Use a private registry/base to avoid SQLModel's global default registry
# being reused across test re-imports (which causes SAWarnings about
# duplicate class names). Each import of this module creates a fresh
# registry and metadata.
_registry = sa_registry()


class ModelBase(SQLModel, registry=_registry):  # type: ignore[call-arg]
    """Base class for all database table models.

    All models should inherit from this class to ensure consistent
    metadata and registry usage. This is critical for Alembic's
    autogenerate feature to work correctly.

    Example:
        ```python
        from app.db.base import ModelBase
        from sqlmodel import Field

        class MyModel(ModelBase, table=True):
            id: int = Field(primary_key=True)
            name: str
        ```
    """

    pass


# Export metadata for Alembic to use in env.py
__all__ = ["ModelBase"]
