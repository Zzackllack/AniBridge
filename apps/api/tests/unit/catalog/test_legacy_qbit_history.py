"""Query mode must still serve the user's pre-existing download history."""

import sqlite3
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.catalog.client import ClientJobs
from app.catalog.qbit_http import router
from test_jobs import NOW, setup_jobs


@pytest.mark.parametrize("endpoint", ["torrents/info", "sync/maindata"])
@pytest.mark.parametrize("public_root", [None, "/client/downloads"])
def test_legacy_and_durable_history_stream_complete_json(
    tmp_path, monkeypatch, endpoint, public_root
):
    from app.api.qbittorrent import projection

    monkeypatch.setattr(projection, "QBIT_PUBLIC_SAVE_PATH", public_root)
    jobs = setup_jobs(tmp_path)
    output = jobs.download_dir / "legacy.mkv"
    output.write_bytes(b"retained-output")
    stamp = "2026-10-01T12:00:00+00:00"
    states = ["completed", "downloading", "failed", "cancelled"]
    with sqlite3.connect(jobs.filename) as db:
        for index, state in enumerate(states):
            db.execute(
                "INSERT INTO job(id,status,progress,total_bytes,speed,eta,result_path) "
                "VALUES(?,?,50,100,12,8,?)",
                (f"old-{index}", state, str(output) if index == 0 else None),
            )
        # Old aliases can also have no job, or reference a removed job. Neither
        # case may prevent the remaining history from reaching the client.
        for index, job in enumerate(["old-0", "old-1", "old-2", "old-3", None, "gone"]):
            db.execute(
                "INSERT INTO clienttask(hash,name,job_id,save_path,category,added_on,state) "
                "VALUES(?,?,?,?,?,?,?)",
                (
                    f"{index + 1:040x}",
                    "Legacy",
                    job,
                    str(jobs.download_dir),
                    "legacy",
                    stamp,
                    "queued",
                ),
            )
    current_hash = "a" * 40
    jobs.admit(
        f"magnet:?xt=urn:btih:{current_hash}&dn=Current&aw_slug=current"
        "&aw_s=1&aw_e=1&aw_lang=German+Dub",
        NOW,
        paused=True,
        category="current",
    )
    before = jobs.filename.read_bytes()
    app = FastAPI()
    app.state.catalog = SimpleNamespace(jobs=jobs, client=ClientJobs(jobs))
    app.include_router(router)
    with TestClient(app) as http:
        response = http.get(f"/api/v2/{endpoint}")
        assert response.status_code == 200
        body = response.json()  # Also consumes and validates the entire stream.
        rows = body if endpoint == "torrents/info" else list(body["torrents"].values())
        assert len(rows) == 7
        by_hash = {row["hash"]: row for row in rows}
        assert set(by_hash) == {f"{index + 1:040x}" for index in range(6)} | {
            current_hash
        }
        for index, state in enumerate(
            ["uploading", "downloading", "error", "pausedDL", "queued", "queued"]
        ):
            assert by_hash[f"{index + 1:040x}"]["state"] == state
        completed = by_hash[f"{1:040x}"]
        assert completed["size"] == output.stat().st_size
        assert completed["dlspeed"] == 0
        assert completed["content_path"] == (
            f"{public_root}/legacy.mkv" if public_root else str(output)
        )
        assert completed["added_on"] == completed["completion_on"] == 1790856000
        assert by_hash[current_hash]["state"] == "pausedDL"
        if endpoint == "torrents/info":
            for category, count in [("legacy", 6), ("current", 1), ("absent", 0)]:
                filtered = http.get(
                    f"/api/v2/{endpoint}", params={"category": category}
                )
                assert filtered.status_code == 200
                assert len(filtered.json()) == count
    assert jobs.filename.read_bytes() == before
