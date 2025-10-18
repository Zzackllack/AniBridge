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
        assert j.source_site == "aniworld"


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
        assert rec.is_fresh and rec.source_site == "aniworld"
        got = get_availability(
            s, slug="slug", season=1, episode=1, language="German Dub"
        )
        assert got and got.available and got.height == 1080
        langs = list_available_languages_cached(
            s, slug="slug", season=1, episode=1
        )
        assert "German Dub" in langs

        ct = upsert_client_task(
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


def test_availability_isolated_by_site(client):
    from sqlmodel import Session
    from app.db import (
        engine,
        upsert_availability,
        list_available_languages_cached,
    )

    with Session(engine) as s:
        upsert_availability(
            s,
            source_site="aniworld",
            slug="dual-show",
            season=1,
            episode=1,
            language="German Dub",
            available=True,
            height=720,
            vcodec="h264",
            provider="aniworld-prov",
        )
        upsert_availability(
            s,
            source_site="sto",
            slug="dual-show",
            season=1,
            episode=1,
            language="English Dub",
            available=True,
            height=1080,
            vcodec="h265",
            provider="sto-prov",
        )

        langs_aniworld = list_available_languages_cached(
            s, source_site="aniworld", slug="dual-show", season=1, episode=1
        )
        langs_sto = list_available_languages_cached(
            s, source_site="sto", slug="dual-show", season=1, episode=1
        )

        assert "German Dub" in langs_aniworld and "English Dub" not in langs_aniworld
        assert "English Dub" in langs_sto and "German Dub" not in langs_sto
