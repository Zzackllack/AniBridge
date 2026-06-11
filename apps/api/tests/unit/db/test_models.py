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
        list_cached_episode_numbers_for_season,
        upsert_strm_mapping,
        get_strm_mapping,
        delete_strm_mapping,
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
        upsert_availability(
            s,
            slug="slug",
            season=1,
            episode=2,
            language="German Dub",
            available=True,
            height=1080,
            vcodec="h264",
            provider="prov",
            extra=None,
        )
        upsert_availability(
            s,
            slug="slug",
            season=1,
            episode=3,
            language="German Dub",
            available=False,
            height=None,
            vcodec=None,
            provider=None,
            extra=None,
        )
        episodes = list_cached_episode_numbers_for_season(
            s, slug="slug", season=1, site="aniworld.to"
        )
        assert episodes == [1, 2]

        upsert_strm_mapping(
            s,
            site="aniworld.to",
            slug="slug",
            season=1,
            episode=1,
            language="German Dub",
            provider=None,
            resolved_url="https://example.com/video.mp4",
            provider_used="VOE",
            resolved_headers=None,
        )
        mapping = get_strm_mapping(
            s,
            site="aniworld.to",
            slug="slug",
            season=1,
            episode=1,
            language="German Dub",
            provider=None,
        )
        assert mapping and mapping.resolved_url == "https://example.com/video.mp4"
        delete_strm_mapping(
            s,
            site="aniworld.to",
            slug="slug",
            season=1,
            episode=1,
            language="German Dub",
            provider=None,
        )
        assert (
            get_strm_mapping(
                s,
                site="aniworld.to",
                slug="slug",
                season=1,
                episode=1,
                language="German Dub",
                provider=None,
            )
            is None
        )

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


def test_replace_canonical_episodes_dedupes_duplicate_numbers(client):
    from sqlmodel import Session, select
    from app.db import (
        CanonicalEpisode,
        engine,
        replace_canonical_episodes,
        upsert_canonical_series,
    )

    with Session(engine) as s:
        upsert_canonical_series(
            s,
            tvdb_id=12345,
            title="Demo Show",
            aliases=["Demo Show"],
        )
        replace_canonical_episodes(
            s,
            tvdb_id=12345,
            episodes=[
                {"season": 1, "episode": 1, "title": "Pilot"},
                {"season": 1, "episode": 1, "title": "Pilot Duplicate"},
                {"season": 1, "episode": 2, "title": "Second"},
            ],
        )
        s.commit()

        rows = s.exec(
            select(CanonicalEpisode).where(CanonicalEpisode.tvdb_id == 12345)
        ).all()

        assert len(rows) == 2
        assert {(row.season, row.episode) for row in rows} == {(1, 1), (1, 2)}


def test_upsert_canonical_series_keeps_aliases_when_omitted(client):
    from sqlmodel import Session, select
    from app.db import CanonicalSeriesAlias, engine, upsert_canonical_series

    with Session(engine) as s:
        upsert_canonical_series(
            s,
            tvdb_id=999,
            title="Demo Show",
            aliases=["Demo Alias"],
        )
        upsert_canonical_series(
            s,
            tvdb_id=999,
            title="Demo Show Renamed",
            aliases=None,
        )
        s.commit()

        aliases = s.exec(
            select(CanonicalSeriesAlias).where(CanonicalSeriesAlias.tvdb_id == 999)
        ).all()

        assert [alias.alias for alias in aliases] == ["Demo Alias"]


def test_replace_provider_catalog_title_keeps_live_generation_intact(client):
    from sqlmodel import Session, select
    from app.db import ProviderCatalogTitle, engine, replace_provider_catalog_title

    with Session(engine) as s:
        replace_provider_catalog_title(
            s,
            provider="aniworld.to",
            slug="demo-show",
            title="Demo Show",
            media_type_hint="series",
            relative_path="/anime/stream/demo-show",
            indexed_generation="gen-live",
        )
        replace_provider_catalog_title(
            s,
            provider="aniworld.to",
            slug="demo-show",
            title="Demo Show Updated",
            media_type_hint="series",
            relative_path="/anime/stream/demo-show-updated",
            indexed_generation="gen-staged",
        )
        s.commit()

        rows = s.exec(
            select(ProviderCatalogTitle).where(
                ProviderCatalogTitle.provider == "aniworld.to"
            )
        ).all()

        assert {(row.slug, row.indexed_generation, row.title) for row in rows} == {
            ("demo-show", "gen-live", "Demo Show"),
            ("demo-show", "gen-staged", "Demo Show Updated"),
        }


def test_replace_provider_catalog_episodes_dedupes_languages_and_host_hints(client):
    from sqlmodel import Session, select
    from app.db import (
        ProviderEpisodeLanguage,
        engine,
        replace_provider_catalog_episodes,
    )

    with Session(engine) as s:
        replace_provider_catalog_episodes(
            s,
            provider="aniworld.to",
            slug="demo-show",
            indexed_generation="gen-1",
            episodes=[
                {
                    "season": 1,
                    "episode": 1,
                    "relative_path": "/anime/stream/demo-show/staffel-1/episode-1",
                    "title_primary": "Pilot",
                    "title_secondary": None,
                    "media_type_hint": "episode",
                    "languages": [
                        {"language": "German Dub", "host_hints": ["VOE", "VOE"]},
                        {"language": "German Dub", "host_hints": ["Filemoon"]},
                    ],
                }
            ],
        )
        s.commit()

        rows = s.exec(select(ProviderEpisodeLanguage)).all()

        assert len(rows) == 1
        assert rows[0].language == "German Dub"
        assert rows[0].host_hints == ["Filemoon", "VOE"]
