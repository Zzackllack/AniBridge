"""Database session management and engine configuration.

This module provides the SQLAlchemy engine and session management utilities.
It centralizes database connection configuration and provides dependency injection
helpers for FastAPI endpoints.
"""

from typing import Generator
from pathlib import Path

from loguru import logger
from sqlmodel import Session, create_engine
from sqlalchemy.pool import NullPool

from app.config import DATA_DIR

# Database URL configuration
DATABASE_URL = f"sqlite:///{(DATA_DIR / 'anibridge_jobs.db').as_posix()}"
logger.debug(f"DATABASE_URL: {DATABASE_URL}")

# Create SQLAlchemy engine with SQLite-specific configuration
# - check_same_thread=False: Allow SQLite to be used with async code
# - NullPool: Ensure connections are closed when sessions end (important for SQLite)
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
    echo=False,  # Set to True for SQL query debugging
)
logger.debug("SQLModel engine created.")


def get_session() -> Generator[Session, None, None]:
    """Dependency for FastAPI endpoints to get a database session.

    This function creates a new database session, yields it for use in the
    endpoint, and ensures it's properly closed after the request completes.

    Usage:
        ```python
        from fastapi import Depends
        from app.db.session import get_session

        @app.get("/items")
        def get_items(session: Session = Depends(get_session)):
            items = session.exec(select(Item)).all()
            return items
        ```

    Yields:
        Session: A SQLModel session for database operations.
    """
    logger.debug("Creating new DB session.")
    try:
        with Session(engine) as session:
            logger.debug("DB session created.")
            yield session
    except Exception as e:
        logger.error(f"Error creating DB session: {e}")
        raise


def dispose_engine() -> None:
    """Dispose the global SQLAlchemy engine to close any pooled connections.

    This helps tests and short-lived runs avoid ResourceWarning: unclosed database.
    Should be called during application shutdown.
    """
    try:
        engine.dispose()
        logger.debug("SQLAlchemy engine disposed.")
    except Exception as e:
        logger.warning(f"Engine dispose error: {e}")


__all__ = ["engine", "get_session", "dispose_engine", "DATABASE_URL"]
