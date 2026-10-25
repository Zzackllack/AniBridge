"""Progress must describe the whole transfer, without completing publication."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.catalog.client import ClientJobs
from app.catalog.qbit_http import router
from app.catalog.transfer_progress import TransferProgress
from test_jobs import NOW, grab, setup_jobs


def test_known_and_estimated_totals_reach_sonarr(tmp_path):
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    claim = jobs.claim(NOW)
    tracker = TransferProgress([{}])
    app = FastAPI()
    app.state.catalog = SimpleNamespace(jobs=jobs, client=ClientJobs(jobs))
    app.include_router(router)
    with TestClient(app) as http:
        for total_field, estimated in (
            ("total_bytes_estimate", True),
            ("total_bytes", False),
        ):
            update = tracker.update(
                0, {"downloaded_bytes": 25, total_field: 100, "speed": 5, "eta": 15}
            )
            assert jobs.heartbeat(job, claim["generation"], NOW + 1, update)
            for endpoint in ("torrents/info", "sync/maindata"):
                body = http.get(f"/api/v2/{endpoint}").json()
                rows = (
                    body if isinstance(body, list) else list(body["torrents"].values())
                )
                row = rows[0]
                assert row["size"] == 100 and row["downloaded"] == 25
                assert row["progress"] == 0.25
                assert row["anibridge_size_estimated"] is estimated
                # Same calculation as Sonarr's qBittorrent adapter and queue UI.
                remaining = int(row["size"] * (1 - row["progress"]))
                assert 100 - remaining / row["size"] * 100 == 25
        update = tracker.finish(0, 100)
        jobs.heartbeat(job, claim["generation"], NOW + 2, update)
        assert 0 < jobs.projection(job)["progress"] < 1
        assert jobs.projection(job)["state"] == "downloading"


def test_tracks_never_treat_video_alone_as_the_whole_download():
    tracker = TransferProgress([{}, {"filesize": 20}])
    first = tracker.update(0, {"downloaded_bytes": 40, "total_bytes": 80, "speed": 10})
    assert first["downloaded_bytes"] == 40
    assert first["total_bytes"] == 100
    assert first["eta"] == 6
    tracker.finish(0, 80)
    audio = tracker.update(1, {"downloaded_bytes": 10, "total_bytes": 20, "eta": 1})
    assert audio["downloaded_bytes"] == 90 and audio["total_bytes"] == 100
    assert tracker.finish(1, 20)["total_bytes"] == 100


def test_unknown_future_track_does_not_invent_a_size_or_eta():
    tracker = TransferProgress([{}, {}])
    first = tracker.update(0, {"downloaded_bytes": 40, "total_bytes": 80, "eta": 4})
    assert first["total_bytes"] is None and first["eta"] is None
    tracker.finish(0, 80)
    last = tracker.update(
        1, {"downloaded_bytes": 5, "total_bytes_estimate": 20, "eta": 3}
    )
    assert last["downloaded_bytes"] == 85 and last["total_bytes"] == 100
    assert last["total_bytes_estimated"] is True
    assert last["eta"] == 3


@pytest.mark.parametrize("total", [None, 0, -1, float("inf"), float("nan"), True])
def test_invalid_totals_remain_unknown(total):
    update = TransferProgress([{}]).update(
        0, {"downloaded_bytes": 25, "total_bytes": total}
    )
    assert update["total_bytes"] is None
    assert update["total_bytes_estimated"] is False


def test_old_estimate_cannot_overwrite_an_exact_size():
    tracker = TransferProgress([{}])
    tracker.update(0, {"downloaded_bytes": 10, "total_bytes": 100})
    update = tracker.update(0, {"downloaded_bytes": 20, "total_bytes_estimate": 150})
    assert update["total_bytes"] == 100
    assert update["total_bytes_estimated"] is False


def test_invalidated_exact_total_does_not_claim_an_exact_size():
    update = TransferProgress([{}]).update(
        0, {"downloaded_bytes": 25, "total_bytes": 20}
    )
    assert update["total_bytes"] is None


def test_failed_estimated_transfer_does_not_leave_an_unlabelled_total(tmp_path):
    jobs = setup_jobs(tmp_path)
    job = jobs.admit(grab(tmp_path), NOW)[0]
    claim = jobs.claim(NOW)
    update = TransferProgress([{}]).update(
        0, {"downloaded_bytes": 25, "total_bytes_estimate": 100}
    )
    jobs.heartbeat(job, claim["generation"], NOW + 1, update)
    jobs.finish(job, claim["generation"], "extraction_error", NOW + 2)
    assert jobs.get(job)["error_code"] == "extraction_error"
    assert jobs.projection(job)["size"] == 0
    assert jobs.get(job)["downloaded_bytes"] == 25
