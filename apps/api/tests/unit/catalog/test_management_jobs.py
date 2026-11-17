"""Completed-missing recovery is explicit, versioned and never automatic."""

import base64
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.catalog.client import ClientJobs
from app.catalog.management import router
from app.catalog.management_auth import ManagementAuth
from test_jobs import NOW, grab, setup_jobs

TOKEN = base64.urlsafe_b64encode(b"m" * 32).decode().rstrip("=")


def _application(jobs):
    app = FastAPI()
    app.state.catalog = SimpleNamespace(jobs=jobs, client=ClientJobs(jobs))
    app.state.management_auth = ManagementAuth(TOKEN)
    app.include_router(router)
    return app


def _headers(version: int | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {TOKEN}"}
    if version is not None:
        headers["If-Match"] = f'"{version}"'
    return headers


def _completed_missing(tmp_path):
    jobs = setup_jobs(tmp_path)
    value = grab(tmp_path)
    job = jobs.admit(value, NOW)[0]
    claim = jobs.claim(NOW)
    output = jobs.download_dir / "verified.mkv"
    output.write_bytes(b"synthetic verified output")
    assert jobs.finish(job, claim["generation"], "ok", NOW + 1, output)
    output.unlink()
    return jobs, value, job


def test_readding_completed_missing_keeps_the_stable_alias(tmp_path):
    jobs, value, job = _completed_missing(tmp_path)
    completed = jobs.get(job)

    # qBittorrent treats an existing hash as a no-op. Resetting the ledger here
    # would re-download a completed import without the operator asking.
    assert jobs.admit(value, NOW + 2) == [job]
    assert jobs.get(job) == completed
    assert jobs.projection(job)["anibridge_output_missing"] is True


def test_management_advertises_and_performs_completed_missing_retry(tmp_path):
    jobs, _value, job = _completed_missing(tmp_path)
    with TestClient(_application(jobs)) as http:
        resource = http.get(f"/api/v1/jobs/{job}", headers=_headers())
        assert resource.status_code == 200
        assert resource.json()["actions"] == ["retry"]
        version = resource.json()["version"]

        assert (
            http.post(
                f"/api/v1/jobs/{job}/retry", json={}, headers=_headers()
            ).status_code
            == 428
        )
        assert (
            http.post(
                f"/api/v1/jobs/{job}/retry",
                json={},
                headers=_headers(version + 1),
            ).status_code
            == 412
        )
        retried = http.post(
            f"/api/v1/jobs/{job}/retry", json={}, headers=_headers(version)
        )
        assert retried.status_code == 202

    row = jobs.get(job)
    assert row["status"] == "queued"
    assert row["progress"] == 0
    assert row["result_path"] is None
    assert jobs.claim(NOW + 3) is not None


def test_management_does_not_offer_retry_for_available_completion(tmp_path):
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    claim = jobs.claim(NOW)
    output = jobs.download_dir / "verified.mkv"
    output.write_bytes(b"synthetic verified output")
    assert jobs.finish(job, claim["generation"], "ok", NOW + 1, output)

    with TestClient(_application(jobs)) as http:
        resource = http.get(f"/api/v1/jobs/{job}", headers=_headers())
        assert resource.status_code == 200
        assert resource.json()["actions"] == []
