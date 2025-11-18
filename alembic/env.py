"""Alembic environment configuration for AniBridge.

This file is responsible for configuring Alembic to work with SQLModel.
It imports the ModelBase metadata from app.db.base and uses the database
engine from app.db.session to ensure consistency with the application.

Key features:
- Uses SQLModel metadata for autogenerate support
- Reuses application's database engine configuration
- Supports both online and offline migration modes
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import application's database configuration
import sys
from pathlib import Path

# Add project root to path to allow importing app modules
project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Import SQLModel metadata and database URL from application
from app.db.base import ModelBase
from app.db.session import DATABASE_URL

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the database URL from the application's configuration
# This ensures Alembic uses the same database as the application
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Add your model's MetaData object here for 'autogenerate' support
# Import all models to ensure they are registered with ModelBase.metadata
from app.db import models  # noqa: F401

target_metadata = ModelBase.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite-specific: support rendering default values
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, 
            target_metadata=target_metadata,
            # SQLite-specific: use batch mode for ALTER operations
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

