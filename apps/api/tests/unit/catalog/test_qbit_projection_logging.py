"""Legacy history must not masquerade as the current catalog transfer in logs."""

from datetime import datetime
from types import SimpleNamespace

from app.api.qbittorrent import projection
from app.catalog.client import ClientJobs
from test_jobs import NOW, grab, setup_jobs


def test_legacy_missing_output_log_explains_recorded_completion(tmp_path, monkeypatch):
    messages = []
    monkeypatch.setattr(
        projection.logger,
        "trace",
        lambda message, *args: messages.append(message.format(*args)),
    )
    alias = SimpleNamespace(
        hash="a" * 40,
        name="private-release-title",
        state="failed",
        save_path="/downloads",
        category="movies",
        added_on=datetime(2026, 1, 1),
        completion_on=None,
    )
    job = SimpleNamespace(
        id="historical-job",
        status="failed",
        progress=100,
        total_bytes=100,
        speed=0,
        eta=0,
        result_path=str(tmp_path / "moved-output.mkv"),
        message="missing_output",
    )
    row = projection.torrent_info_record(alias, job)
    assert row["state"] == "missingFiles" and row["progress"] == 1
    (message,) = messages
    assert message.startswith("Legacy job projection:")
    assert "job_id=historical-job" in message
    assert "stored_status=failed" in message
    assert "recorded_transfer_progress=1.0" in message
    assert "output_missing=True" in message
    assert "private-release-title" not in message


def test_catalog_log_reports_actual_bytes_and_unknown_or_estimated_total(
    tmp_path, monkeypatch
):
    from app.catalog import client

    messages = []
    monkeypatch.setattr(
        client.logger,
        "trace",
        lambda message, *args: messages.append(message.format(*args)),
    )
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    claim = jobs.claim(NOW)
    views = ClientJobs(jobs)
    jobs.heartbeat(
        job, claim["generation"], NOW + 1, {"downloaded_bytes": 25, "speed": 5}
    )
    unknown = next(views.views())
    assert unknown["size"] == 0 and unknown["downloaded"] == 25
    assert "Catalog job projection:" in messages[-1]
    assert f"job_id={job}" in messages[-1]
    assert "downloaded_bytes=25" in messages[-1]
    assert "total_bytes=None, size_basis=unknown" in messages[-1]
    jobs.heartbeat(
        job,
        claim["generation"],
        NOW + 2,
        {
            "downloaded_bytes": 50,
            "total_bytes": 100,
            "total_bytes_estimated": True,
            "speed": 5,
        },
    )
    estimated = next(views.views())
    assert estimated["progress"] == 0.5
    assert "size_basis=estimated" in messages[-1]
    assert "transfer_progress=0.5" in messages[-1]
    assert "Example.S01E02" not in "\n".join(messages)
