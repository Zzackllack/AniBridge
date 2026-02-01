def test_job_crud_and_cleanup(client):
    from sqlmodel import Session
    from app.db import create_job, get_job, update_job, cleanup_dangling_jobs, engine

    with Session(engine) as s:
        job = create_job(s)
        assert get_job(s, job.id)
        update = update_job(s, job.id, status="downloading", progress=50.0, speed=10)
        assert update and update.status == "downloading" and update.progress == 50.0
        # mark as queued to be cleaned as dangling
        update_job(s, job.id, status="queued")
        cleaned = cleanup_dangling_jobs(s)
        assert cleaned >= 1
        j = get_job(s, job.id)
        assert j and j.status == "failed"


def test_availability_and_clienttask_crud(client):
    from sqlmodel import Session
    from app.db import (
        engine,
        upsert_availability,
        get_availability,
        list_available_languages_cached,
        upsert_client_task,
        get_client_task,
        delete_client_task,
    )

    with Session(engine) as s:
        rec = upsert_availability(
            s,
            slug="slug",
            season=1,
            episode=1,
            language="German Dub",
            available=True,
            height=1080,
            vcodec="h264",
            provider="prov",
            extra={"x": 1},
        )
        assert rec.is_fresh
        got = get_availability(
            s, slug="slug", season=1, episode=1, language="German Dub"
        )
        assert got and got.available and got.height == 1080
        langs = list_available_languages_cached(s, slug="slug", season=1, episode=1)
        assert "German Dub" in langs

        upsert_client_task(
            s,
            hash="abc",
            name="Name",
            slug="slug",
            season=1,
            episode=1,
            language="German Dub",
            save_path="/tmp",
            category="anime",
            job_id="job-1",
            state="downloading",
        )
        assert get_client_task(s, "abc")
        delete_client_task(s, "abc")
        assert get_client_task(s, "abc") is None
