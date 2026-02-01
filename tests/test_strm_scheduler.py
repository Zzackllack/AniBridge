import errno
import threading
from pathlib import Path

from sqlmodel import Session



def _setup_scheduler(tmp_path, monkeypatch):
    """
    Prepare a test scheduler environment and return the scheduler module.

    Sets environment variables ANIBRIDGE_UPDATE_CHECK, DATA_DIR, and DOWNLOAD_DIR for the test run, removes cached app modules related to configuration, database, and scheduler from sys.modules to ensure a fresh import, and initializes the test database tables. Finally imports and returns the app.core.scheduler module.

    Returns:
        module: The imported `app.core.scheduler` module.
    """
    monkeypatch.setenv("ANIBRIDGE_UPDATE_CHECK", "0")
    data_dir = tmp_path / "data"
    download_dir = tmp_path / "downloads"
    data_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DATA_DIR", str(data_dir))
    monkeypatch.setenv("DOWNLOAD_DIR", str(download_dir))

    import sys

    for mod in ("app.config", "app.db", "app.db.models", "app.core.scheduler"):
        if mod in sys.modules:
            del sys.modules[mod]

    from app.db import create_db_and_tables

    create_db_and_tables()

    import app.core.scheduler as scheduler

    return scheduler


def _create_job():
    """
    Create a new job in the test database for the source site "aniworld.to" and return its identifier.

    Returns:
        The created job's id.
    """
    from app.db import create_job, engine

    with Session(engine) as session:
        return create_job(session, source_site="aniworld.to").id


def _get_job(job_id: str):
    """
    Retrieve a job record from the database by its identifier.

    Parameters:
        job_id (str): Identifier of the job to retrieve.

    Returns:
        The job record matching `job_id`, or `None` if no such job exists.
    """
    from app.db import get_job, engine

    with Session(engine) as session:
        return get_job(session, job_id)


def test_run_strm_creates_file_and_updates_job(tmp_path, monkeypatch):
    scheduler = _setup_scheduler(tmp_path, monkeypatch)
    monkeypatch.setattr(scheduler, "build_episode", lambda **kwargs: object())
    monkeypatch.setattr(
        scheduler,
        "get_direct_url_with_fallback",
        lambda *args, **kwargs: ("https://example.com/video.mp4", "VOE"),
    )

    job_id = _create_job()
    req = {
        "slug": "my-show",
        "season": 1,
        "episode": 2,
        "language": "German Dub",
        "title_hint": "My Show",
        "site": "aniworld.to",
    }
    scheduler._run_strm(job_id, req, threading.Event())

    job = _get_job(job_id)
    assert job is not None
    assert job.status == "completed"
    assert job.result_path

    out_path = Path(job.result_path)
    assert out_path.exists()
    data = out_path.read_bytes()
    assert data == b"https://example.com/video.mp4\n"
    assert b"\r\n" not in data


def test_run_strm_marks_failed_on_invalid_url(tmp_path, monkeypatch):
    """Test that _run_strm fails when given a non-HTTP(S) URL."""
    scheduler = _setup_scheduler(tmp_path, monkeypatch)
    monkeypatch.setattr(scheduler, "build_episode", lambda **kwargs: object())
    monkeypatch.setattr(
        scheduler,
        "get_direct_url_with_fallback",
        lambda *args, **kwargs: ("ftp://example.com/video.mp4", "VOE"),
    )

    job_id = _create_job()
    req = {"slug": "my-show", "season": 1, "episode": 1}
    scheduler._run_strm(job_id, req, threading.Event())

    job = _get_job(job_id)
    assert job is not None
    assert job.status == "failed"
    assert job.message
    assert "STRM url must be http(s)" in job.message


def test_run_strm_marks_failed_on_unwritable_directory(tmp_path, monkeypatch):
    scheduler = _setup_scheduler(tmp_path, monkeypatch)
    monkeypatch.setattr(scheduler, "build_episode", lambda **kwargs: object())
    monkeypatch.setattr(
        scheduler,
        "get_direct_url_with_fallback",
        lambda *args, **kwargs: ("https://example.com/video.mp4", "VOE"),
    )
    monkeypatch.setattr(
        scheduler,
        "allocate_unique_strm_path",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            OSError(errno.EACCES, "Permission denied")
        ),
    )

    job_id = _create_job()
    req = {"slug": "my-show", "season": 1, "episode": 1}
    scheduler._run_strm(job_id, req, threading.Event())

    job = _get_job(job_id)
    assert job is not None
    assert job.status == "failed"
    assert job.message
    assert "Download dir not writable" in job.message
