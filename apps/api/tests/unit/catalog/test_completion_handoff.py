"""Moving imported bytes must not rewrite a proven transfer as a failure."""

import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine

from app.catalog.client import ClientJobs
from app.catalog.jobs import Jobs
from app.catalog.qbit_http import get_session, router
from test_jobs import NOW, grab, setup_jobs


def test_import_move_preserves_completion_and_explicit_retry(tmp_path):
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    claim = jobs.claim(NOW)
    output = jobs.download_dir / "verified.mkv"
    output.write_bytes(b"synthetic verified output")
    jobs.finish(job, claim["generation"], "ok", NOW + 1, output)
    completed = jobs.get(job)
    assert jobs.projection(job)["size"] == output.stat().st_size
    library = tmp_path / "library.mkv"
    output.rename(library)
    restarted = Jobs(jobs.filename, jobs.download_dir, jobs.providers)
    restarted.recover(NOW + 2, startup=True)
    assert restarted.get(job) == completed
    row = next(ClientJobs(restarted).views())
    assert row["state"] == "missingFiles" and row["progress"] == 1
    assert row["content_path"] == ""
    assert row["anibridge_output_missing"] is True
    assert restarted.claim(NOW + 1000) is None
    # Only an explicit operator action can repeat a completed transfer.
    restarted.action(job, "retry", NOW + 1001, completed["version"])
    assert restarted.get(job)["progress"] == 0
    assert restarted.claim(NOW + 1002) is not None
    assert library.read_bytes() == b"synthetic verified output"


def test_historical_missing_output_is_visible_without_rewriting_ledger(tmp_path):
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    claim = jobs.claim(NOW)
    output = jobs.download_dir / "verified.mkv"
    output.write_bytes(b"synthetic output")
    jobs.finish(job, claim["generation"], "ok", NOW + 1, output)
    output.unlink()
    with sqlite3.connect(jobs.filename) as db:
        db.execute(
            "UPDATE job SET status='failed',message='missing_output' WHERE id=?", (job,)
        )
        db.execute(
            "UPDATE durable_request SET error_code='missing_output' WHERE job_id=?",
            (job,),
        )
    before = jobs.filename.read_bytes()
    row = jobs.projection(job)
    assert row["state"] == "missingFiles" and row["content_path"] == ""
    assert row["progress"] == 1
    assert jobs.filename.read_bytes() == before


def test_other_failure_does_not_become_completed(tmp_path):
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    claim = jobs.claim(NOW)
    jobs.finish(job, claim["generation"], "extraction_error", NOW + 1)
    assert jobs.projection(job)["state"] == "error"
    assert jobs.projection(job)["progress"] < 1


@pytest.mark.parametrize("durable", [False, True])
def test_missing_outputs_stream_safely_and_do_not_return_files(tmp_path, durable):
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    claim = jobs.claim(NOW)
    output = jobs.download_dir / "verified.mkv"
    output.write_bytes(b"synthetic output")
    jobs.finish(job, claim["generation"], "ok", NOW + 1, output)
    output.unlink()
    with sqlite3.connect(jobs.filename) as db:
        if not durable:
            db.execute("DELETE FROM durable_request WHERE job_id=?", (job,))
            db.execute(
                "UPDATE job SET status='failed',message='missing_output' WHERE id=?",
                (job,),
            )
    before = jobs.filename.read_bytes()
    app = FastAPI()
    app.state.catalog = SimpleNamespace(jobs=jobs, client=ClientJobs(jobs))
    engine = create_engine(f"sqlite:///{jobs.filename}")

    def session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_session] = session
    app.include_router(router)
    with TestClient(app) as http:
        for endpoint in ("torrents/info", "sync/maindata"):
            body = http.get(f"/api/v2/{endpoint}").json()
            rows = body if isinstance(body, list) else list(body["torrents"].values())
            assert rows[0]["state"] == "missingFiles"
            assert rows[0]["content_path"] == ""
            assert rows[0]["anibridge_output_missing"] is True
        assert (
            http.get("/api/v2/torrents/files", params={"hash": rows[0]["hash"]}).json()
            == []
        )
    assert jobs.filename.read_bytes() == before
    engine.dispose()
