"""Repeated client polling preserves transfer facts without logging every job."""

from datetime import datetime
from types import SimpleNamespace

from app.api.qbittorrent import projection
from loguru import logger

from app.catalog.client import ClientJobs
from test_jobs import NOW, grab, setup_jobs


def test_legacy_missing_output_polling_is_quiet(tmp_path, monkeypatch):
    messages = []
    monkeypatch.setattr(
        logger,
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
    assert row["state"] == "uploading" and row["progress"] == 1
    assert projection.torrent_info_record(alias, job) == row
    assert messages == []


def test_catalog_polling_retains_unknown_and_estimated_totals_without_logs(
    tmp_path, monkeypatch
):
    messages = []
    monkeypatch.setattr(
        logger,
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
    assert estimated["anibridge_size_estimated"] is True
    assert next(views.views()) == estimated
    assert messages == []
