"""Tests for Alembic migration utilities and database schema management."""

import pytest
from pathlib import Path
import tempfile
import shutil


def test_migration_utilities_available():
    """Test that migration utility functions are importable and callable."""
    from app.db.migrations import (
        run_migrations,
        get_current_revision,
        check_migrations_status,
        get_alembic_config,
    )
    
    # Verify functions are callable
    assert callable(run_migrations)
    assert callable(get_current_revision)
    assert callable(check_migrations_status)
    assert callable(get_alembic_config)


def test_alembic_config_exists():
    """Test that alembic.ini configuration file exists."""
    from app.db.migrations import get_alembic_config
    
    config = get_alembic_config()
    assert config is not None
    assert config.config_file_name is not None
    assert Path(config.config_file_name).exists()


def test_migration_status(client):
    """Test migration status checking after setup."""
    from app.db.migrations import check_migrations_status, get_current_revision
    
    # Check migration status
    status = check_migrations_status()
    assert "current_revision" in status
    assert status["current_revision"] is not None
    assert status["current_revision"] != "unknown"
    
    # Get current revision
    revision = get_current_revision()
    assert revision is not None
    assert revision != "base"
    assert revision != "unknown"


def test_database_tables_created(client):
    """Test that all expected tables are created after migrations."""
    from sqlmodel import Session, text
    from app.db import engine
    
    with Session(engine) as session:
        # Check that alembic version table exists
        result = session.exec(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
        )
        assert result.fetchone() is not None
        
        # Check that our model tables exist
        expected_tables = ["job", "episodeavailability", "clienttask"]
        for table in expected_tables:
            result = session.exec(
                text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
            )
            assert result.fetchone() is not None, f"Table {table} should exist"


def test_database_indexes_created(client):
    """Test that expected indexes are created."""
    from sqlmodel import Session, text
    from app.db import engine
    
    with Session(engine) as session:
        # Check for some key indexes
        expected_indexes = [
            "ix_job_status",
            "ix_job_created_at",
            "ix_episodeavailability_checked_at",
            "ix_clienttask_state",
        ]
        
        for index_name in expected_indexes:
            result = session.exec(
                text(f"SELECT name FROM sqlite_master WHERE type='index' AND name='{index_name}'")
            )
            assert result.fetchone() is not None, f"Index {index_name} should exist"


def test_models_work_after_migration(client):
    """Test that models work correctly after migration setup."""
    from sqlmodel import Session
    from app.db import (
        create_job,
        get_job,
        upsert_availability,
        get_availability,
        upsert_client_task,
        get_client_task,
        engine,
    )
    
    with Session(engine) as session:
        # Test Job CRUD
        job = create_job(session)
        assert job.id is not None
        assert get_job(session, job.id) is not None
        
        # Test EpisodeAvailability CRUD
        avail = upsert_availability(
            session,
            slug="test",
            season=1,
            episode=1,
            language="English",
            available=True,
            height=1080,
            vcodec="h264",
            provider="test",
        )
        assert avail is not None
        retrieved = get_availability(
            session, slug="test", season=1, episode=1, language="English"
        )
        assert retrieved is not None
        assert retrieved.height == 1080
        
        # Test ClientTask CRUD
        task = upsert_client_task(
            session,
            hash="abc123",
            name="Test Task",
            slug="test",
            season=1,
            episode=1,
            language="English",
            save_path="/tmp",
            category="anime",
            job_id=job.id,
        )
        assert task is not None
        assert get_client_task(session, "abc123") is not None


def test_migration_idempotency():
    """Test that running migrations multiple times is safe."""
    from app.db.migrations import run_migrations, get_current_revision
    
    # Get initial revision
    initial_revision = get_current_revision()
    
    # Run migrations again
    run_migrations()
    
    # Revision should be the same (no new migrations applied)
    final_revision = get_current_revision()
    assert initial_revision == final_revision


def test_alembic_version_table_exists(client):
    """Test that Alembic's version tracking table exists."""
    from sqlmodel import Session, text
    from app.db import engine
    
    with Session(engine) as session:
        # Check alembic_version table
        result = session.exec(
            text("SELECT version_num FROM alembic_version")
        )
        version = result.fetchone()
        assert version is not None
        assert len(version) > 0  # Should have a version number


def test_database_url_configuration():
    """Test that database URL is properly configured."""
    from app.db.session import DATABASE_URL
    from app.config import DATA_DIR
    
    assert DATABASE_URL is not None
    assert "sqlite:///" in DATABASE_URL
    assert str(DATA_DIR) in DATABASE_URL or "anibridge_jobs.db" in DATABASE_URL


def test_model_base_metadata():
    """Test that ModelBase has proper metadata configuration."""
    from app.db.base import ModelBase
    from app.db.models import Job, EpisodeAvailability, ClientTask
    
    # Check metadata exists
    assert ModelBase.metadata is not None
    
    # Check that our models are registered in metadata
    table_names = [table.name for table in ModelBase.metadata.tables.values()]
    assert "job" in table_names
    assert "episodeavailability" in table_names
    assert "clienttask" in table_names


def test_session_management():
    """Test database session creation and cleanup."""
    from app.db.session import get_session
    
    # Get a session via the dependency
    session_gen = get_session()
    session = next(session_gen)
    
    assert session is not None
    
    # Clean up
    try:
        next(session_gen)
    except StopIteration:
        pass  # Expected - generator should be exhausted


def test_engine_disposal():
    """Test that engine can be disposed properly."""
    from app.db.session import dispose_engine
    
    # Should not raise any exceptions
    dispose_engine()
