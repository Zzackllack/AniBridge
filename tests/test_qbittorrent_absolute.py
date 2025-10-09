from __future__ import annotations

from sqlmodel import Session

from app.db import engine, create_job, upsert_client_task, update_job


def _seed_absolute_task(session: Session, *, absolute: int) -> None:
    job = create_job(session)
    update_job(session, job.id, status="downloading", progress=10.0)
    upsert_client_task(
        session,
        hash=f"h{absolute}",
        name=f"Series ABS {absolute}",
        slug="series-abs",
        season=2,
        episode=1,
        language="German Dub",
        save_path="/tmp",
        category="anime",
        job_id=job.id,
        state="downloading",
        absolute_number=absolute,
    )


def test_sync_maindata_includes_absolute_metadata(client):
    with Session(engine) as session:
        _seed_absolute_task(session, absolute=5)

    data = client.get("/api/v2/sync/maindata").json()
    torrents = data["torrents"]
    assert "h5" in torrents
    assert torrents["h5"]["anibridgeAbsolute"] == 5


def test_torrents_info_includes_absolute_metadata(client):
    with Session(engine) as session:
        _seed_absolute_task(session, absolute=7)

    items = client.get("/api/v2/torrents/info").json()
    assert items[0]["hash"] == "h7"
    assert items[0]["anibridgeAbsolute"] == 7
