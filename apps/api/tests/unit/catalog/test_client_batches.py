"""All-job transitions remain finite batches even after history accumulates."""

from contextlib import closing
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.catalog.client import ClientJobs
from app.catalog.qbit_http import router
from test_jobs import setup_jobs, NOW


def test_all_pause_resume_batches_distinct_jobs_and_preserves_terminal_states(tmp_path):
    jobs = setup_jobs(tmp_path)
    ids = []
    for number in range(205):
        value = (
            f"magnet:?xt=urn:btih:{number + 1:040x}&dn=Example&aw_slug=example"
            f"&aw_s=1&aw_e={number + 1}&aw_lang=German+Dub"
        )
        ids.append(jobs.admit(value, NOW)[0])
    jobs.action(ids[0], "cancel", NOW)
    client = ClientJobs(jobs)
    with closing(jobs.db()) as db, db:
        db.execute(
            "INSERT INTO clienttask SELECT ?,name,slug,season,episode,language,site,job_id,save_path,category,added_on,completion_on,state FROM clienttask WHERE job_id=?",
            ("f" * 40, ids[1]),
        )
    batches = list(client.job_batches("all"))
    assert [len(batch) for batch in batches] == [100, 100, 5]
    assert {job for batch in batches for job in batch} == set(ids)
    assert sum(map(len, batches)) == len(ids)
    app = FastAPI()
    app.state.catalog = SimpleNamespace(jobs=jobs, client=client)
    app.include_router(router)
    with TestClient(app) as http:
        assert (
            http.post("/api/v2/torrents/pause", data={"hashes": "all"}).status_code
            == 200
        )
        assert jobs.get(ids[0])["status"] == "cancelled"
        assert all(jobs.get(job)["status"] == "paused" for job in ids[1:])
        assert (
            http.post("/api/v2/torrents/resume", data={"hashes": "all"}).status_code
            == 200
        )
        assert jobs.get(ids[0])["status"] == "cancelled"
        assert all(jobs.get(job)["status"] == "queued" for job in ids[1:])
        assert (
            http.post(
                "/api/v2/torrents/pause",
                data={"hashes": "|".join(f"{n + 1:040x}" for n in range(101))},
            ).status_code
            == 400
        )
        assert all(jobs.get(job)["status"] == "queued" for job in ids[1:])


def test_explicit_hashes_accept_uppercase_and_do_not_touch_other_jobs(tmp_path):
    jobs = setup_jobs(tmp_path)
    value = (
        "magnet:?xt=urn:btih:"
        + "a" * 40
        + "&dn=Example&aw_slug=example&aw_s=1&aw_e=1&aw_lang=German+Dub"
    )
    job = jobs.admit(value, NOW)[0]
    client = ClientJobs(jobs)
    assert list(client.job_batches("A" * 40)) == [[job]]
    assert list(client.job_batches("b" * 40)) == []
    with pytest.raises(ValueError):
        list(client.job_batches("invalid"))
