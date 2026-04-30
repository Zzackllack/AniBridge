import errno
import threading
import time
from concurrent.futures import Future
from pathlib import Path

from sqlmodel import Session


def _setup_scheduler(tmp_path, monkeypatch, *, strm_proxy_mode: str = "direct"):
    """
    Prepare a test scheduler environment configured for STRM proxy behavior and return the scheduler module.

    Sets environment variables for test data and download directories, database startup behavior, and STRM proxy configuration; clears related app modules from the import cache to ensure a fresh import; creates database tables required for tests; and imports the app.core.scheduler module.

    Parameters:
        strm_proxy_mode (str): STRM proxy mode to configure for the test environment. Expected values include "direct" and "proxy".

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
    monkeypatch.setenv("DB_MIGRATE_ON_STARTUP", "0")
    monkeypatch.setenv("STRM_PROXY_MODE", strm_proxy_mode)
    monkeypatch.setenv("STRM_PROXY_AUTH", "none")
    if strm_proxy_mode == "proxy":
        monkeypatch.setenv("STRM_PUBLIC_BASE_URL", "https://anibridge.test")

    import sys

    for mod in (
        "app.config",
        "app.db",
        "app.db.models",
        "app.core.strm_proxy",
        "app.core.strm_proxy.auth",
        "app.core.strm_proxy.cache",
        "app.core.strm_proxy.hls",
        "app.core.strm_proxy.resolver",
        "app.core.strm_proxy.types",
        "app.core.strm_proxy.urls",
        "app.core.scheduler",
    ):
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
    scheduler = _setup_scheduler(tmp_path, monkeypatch, strm_proxy_mode="direct")
    monkeypatch.setattr(
        scheduler,
        "resolve_direct_url",
        lambda identity: ("https://example.com/video.mp4", "VOE"),
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
    scheduler = _setup_scheduler(tmp_path, monkeypatch, strm_proxy_mode="direct")
    monkeypatch.setattr(
        scheduler,
        "resolve_direct_url",
        lambda identity: ("ftp://example.com/video.mp4", "VOE"),
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
    scheduler = _setup_scheduler(tmp_path, monkeypatch, strm_proxy_mode="direct")
    monkeypatch.setattr(
        scheduler,
        "resolve_direct_url",
        lambda identity: ("https://example.com/video.mp4", "VOE"),
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


def test_run_strm_creates_proxy_url(tmp_path, monkeypatch):
    """
    Verifies that when STRM proxy mode is enabled, running _run_strm produces a proxy-served URL file and completes the job.

    Asserts the job status becomes "completed", a non-empty result_path is written, the result file exists, and its contents start with the expected proxy URL prefix.
    """
    scheduler = _setup_scheduler(tmp_path, monkeypatch, strm_proxy_mode="proxy")
    monkeypatch.setattr(
        scheduler,
        "resolve_direct_url",
        lambda identity: ("https://example.com/video.mp4", "VOE"),
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
    data = out_path.read_text(encoding="utf-8")
    assert data.startswith("https://anibridge.test/strm/stream?")

    from app.db import get_strm_mapping, engine

    with Session(engine) as session:
        mapping = get_strm_mapping(
            session,
            site=req["site"],
            slug=req["slug"],
            season=req["season"],
            episode=req["episode"],
            language=req["language"],
            provider=None,
        )
        assert mapping is not None
        assert mapping.resolved_url == "https://example.com/video.mp4"
        assert mapping.provider_used == "VOE"


def test_progress_updater_coalesces_bursty_db_writes(tmp_path, monkeypatch):
    scheduler = _setup_scheduler(tmp_path, monkeypatch, strm_proxy_mode="direct")
    monkeypatch.setattr(scheduler, "JOB_PROGRESS_FLUSH_SECONDS", 60.0)

    writes: list[dict[str, object]] = []

    class FakeSession:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeReporter:
        def __init__(self, label: str):
            self.label = label

        def update(self, snapshot):
            del snapshot

        def close(self):
            return None

    monkeypatch.setattr(scheduler, "Session", lambda _engine: FakeSession())
    monkeypatch.setattr(scheduler, "ProgressReporter", FakeReporter)
    monkeypatch.setattr(
        scheduler,
        "update_job",
        lambda _session, job_id, **fields: writes.append({"job_id": job_id, **fields}),
    )

    callback, writer = scheduler._progress_updater("job-1", threading.Event())
    callback(
        {
            "status": "downloading",
            "downloaded_bytes": 1024,
            "total_bytes": 10_000,
            "speed": 1000,
        }
    )
    callback(
        {
            "status": "downloading",
            "downloaded_bytes": 2048,
            "total_bytes": 10_000,
            "speed": 2000,
            "eta": 5,
        }
    )
    writer.close(flush=True)

    assert len(writes) == 1
    assert writes[0]["job_id"] == "job-1"
    assert writes[0]["downloaded_bytes"] == 2048
    assert writes[0]["total_bytes"] == 10_000
    assert writes[0]["speed"] == 2000.0
    assert writes[0]["eta"] == 5


def test_progress_updater_flushes_without_final_close(tmp_path, monkeypatch):
    scheduler = _setup_scheduler(tmp_path, monkeypatch, strm_proxy_mode="direct")
    monkeypatch.setattr(scheduler, "JOB_PROGRESS_FLUSH_SECONDS", 0.01)

    writes: list[dict[str, object]] = []

    class FakeSession:
        def __enter__(self):
            return object()

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeReporter:
        def __init__(self, label: str):
            self.label = label

        def update(self, snapshot):
            del snapshot

        def close(self):
            return None

    monkeypatch.setattr(scheduler, "Session", lambda _engine: FakeSession())
    monkeypatch.setattr(scheduler, "ProgressReporter", FakeReporter)
    monkeypatch.setattr(
        scheduler,
        "update_job",
        lambda _session, job_id, **fields: writes.append({"job_id": job_id, **fields}),
    )

    callback, writer = scheduler._progress_updater("job-2", threading.Event())
    callback(
        {
            "status": "downloading",
            "downloaded_bytes": 5000,
            "total_bytes": 10_000,
            "speed": 4000,
            "eta": 1,
        }
    )
    writer.close(flush=False)
    deadline = time.monotonic() + 0.5
    while time.monotonic() < deadline:
        if writes:
            break
        time.sleep(0.01)

    assert writes == []


def test_start_scheduled_job_cleans_up_fast_finishing_runner(tmp_path, monkeypatch):
    scheduler = _setup_scheduler(tmp_path, monkeypatch, strm_proxy_mode="direct")

    class ImmediateExecutor:
        def submit(self, runner, job_id, req, stop_event):
            fut = Future()
            runner(job_id, req, stop_event)
            fut.set_result(None)
            return fut

    def fake_runner(job_id, req, stop_event):
        del req, stop_event
        with scheduler.RUNNING_LOCK:
            assert job_id in scheduler.RUNNING
            scheduler.RUNNING.pop(job_id, None)

    with scheduler.RUNNING_LOCK:
        scheduler.RUNNING.clear()

    monkeypatch.setattr(scheduler, "init_executor", lambda: None)
    monkeypatch.setattr(scheduler, "EXECUTOR", ImmediateExecutor())
    monkeypatch.setattr(scheduler, "_run_download", fake_runner)

    scheduler.start_scheduled_job("job-fast", {})

    with scheduler.RUNNING_LOCK:
        assert "job-fast" not in scheduler.RUNNING
