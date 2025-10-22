"""Alembic migration utilities for automatic schema management.

This module provides functions to automatically run Alembic migrations
on application startup, ensuring the database schema is always up-to-date.

The run_migrations() function should be called during application startup
(in the lifespan context) before any database operations occur.
"""

from pathlib import Path
from loguru import logger
from alembic import command
from alembic.config import Config


def get_alembic_config() -> Config:
    """Create and configure an Alembic Config object.
    
    Returns:
        Config: Configured Alembic config pointing to the project's alembic.ini
    """
    # Get the project root directory (where alembic.ini is located)
    project_root = Path(__file__).resolve().parents[2]
    alembic_ini = project_root / "alembic.ini"
    
    if not alembic_ini.exists():
        raise FileNotFoundError(
            f"alembic.ini not found at {alembic_ini}. "
            "Ensure Alembic is initialized properly."
        )
    
    # Create Alembic config
    alembic_cfg = Config(str(alembic_ini))
    
    # Set the script location (where migrations are stored)
    alembic_cfg.set_main_option("script_location", str(project_root / "alembic"))
    
    return alembic_cfg


def run_migrations() -> None:
    """Run all pending Alembic migrations to bring the database up to date.
    
    This function should be called during application startup to ensure
    the database schema matches the current model definitions.
    
    It's safe to call this multiple times - if no migrations are pending,
    nothing will happen.
    
    Raises:
        Exception: If migration fails for any reason
    """
    try:
        logger.info("Running Alembic migrations...")
        alembic_cfg = get_alembic_config()
        
        # Run migrations to the latest version (head)
        command.upgrade(alembic_cfg, "head")
        
        logger.success("Alembic migrations completed successfully.")
    except Exception as e:
        logger.error(f"Failed to run Alembic migrations: {e}")
        raise


def get_current_revision() -> str:
    """Get the current database schema revision.
    
    Returns:
        str: The current revision hash, or "base" if no migrations have been applied
    """
    try:
        from alembic.runtime.migration import MigrationContext
        from app.db.session import engine
        
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current = context.get_current_revision()
            return current if current else "base"
    except Exception as e:
        logger.warning(f"Failed to get current revision: {e}")
        return "unknown"


def check_migrations_status() -> dict:
    """Check the status of database migrations.
    
    Returns:
        dict: Migration status information including:
            - current_revision: Current database schema version
            - pending_migrations: Number of migrations not yet applied (if determinable)
    """
    try:
        alembic_cfg = get_alembic_config()
        current = get_current_revision()
        
        return {
            "current_revision": current,
            "config_location": alembic_cfg.config_file_name,
        }
    except Exception as e:
        logger.warning(f"Failed to check migration status: {e}")
        return {
            "current_revision": "unknown",
            "error": str(e),
        }


__all__ = [
    "run_migrations",
    "get_current_revision", 
    "check_migrations_status",
    "get_alembic_config",
]
