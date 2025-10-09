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
        got = get_availability(s, slug="slug", season=1, episode=1, language="German Dub")
        assert got and got.available and got.height == 1080
        langs = list_available_languages_cached(s, slug="slug", season=1, episode=1)
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


def test_episode_number_mapping_crud(client):
    from sqlmodel import Session
    from app.db import (
        engine,
        upsert_episode_mapping,
        get_episode_mapping_by_absolute,
        get_episode_mapping_by_season_episode,
        list_episode_mappings_for_series,
    )

    with Session(engine) as s:
        first = upsert_episode_mapping(
            s,
            series_slug="series-a",
            absolute_number=1,
            season_number=1,
            episode_number=1,
            episode_title="Pilot",
        )
        assert first.id is not None
        assert first.last_synced_at is not None

        fetched = get_episode_mapping_by_absolute(
            s, series_slug="series-a", absolute_number=1
        )
        assert fetched and fetched.season_number == 1 and fetched.episode_number == 1

        updated = upsert_episode_mapping(
            s,
            series_slug="series-a",
            absolute_number=1,
            season_number=1,
            episode_number=1,
            episode_title="Pilot (Updated)",
        )
        assert updated.id == first.id
        assert updated.episode_title == "Pilot (Updated)"
        assert updated.last_synced_at >= first.last_synced_at

        upsert_episode_mapping(
            s,
            series_slug="series-a",
            absolute_number=2,
            season_number=1,
            episode_number=2,
            episode_title="Second",
        )

        items = list_episode_mappings_for_series(s, series_slug="series-a")
        assert len(items) == 2
        assert {m.absolute_number for m in items} == {1, 2}

        # Re-using the same season/episode should update the existing row instead of duplicating
        remapped = upsert_episode_mapping(
            s,
            series_slug="series-a",
            absolute_number=5,
            season_number=1,
            episode_number=1,
            episode_title="Remap",
        )
        assert remapped.id == first.id
        assert remapped.absolute_number == 5

        by_pair = get_episode_mapping_by_season_episode(
            s, series_slug="series-a", season_number=1, episode_number=1
        )
        assert by_pair and by_pair.absolute_number == 5
