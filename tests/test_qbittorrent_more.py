import xml.etree.ElementTree as ET


def test_add_missing_urls_returns_400(client):
    r = client.post("/api/v2/torrents/add", data={})
    assert r.status_code == 400


def test_edit_and_remove_categories(client):
    # create new category
    r = client.post(
        "/api/v2/torrents/createCategory",
        data={"category": "temp", "savePath": "/tmp"},
    )
    assert r.status_code == 200

    # edit category savePath
    r = client.post(
        "/api/v2/torrents/editCategory",
        data={"category": "temp", "savePath": "/var"},
    )
    assert r.status_code == 200

    cats = client.get("/api/v2/torrents/categories").json()
    assert cats["temp"]["savePath"] == "/var"

    # remove category
    r = client.post("/api/v2/torrents/removeCategories", data={"categories": "temp"})
    assert r.status_code == 200
    cats = client.get("/api/v2/torrents/categories").json()
    assert "temp" not in cats


def test_sync_maindata_state_mapping(client):
    # Prepare jobs and client tasks directly in DB
    from sqlmodel import Session
    from app.db import engine, create_job, update_job, upsert_client_task

    with Session(engine) as s:
        # completed
        j1 = create_job(s)
        update_job(s, j1.id, status="completed", progress=100.0, total_bytes=123)
        upsert_client_task(
            s,
            hash="h1",
            name="A",
            slug="slug",
            season=1,
            episode=1,
            language="German Dub",
            save_path=None,
            category=None,
            job_id=j1.id,
            state="downloading",
        )
        # failed
        j2 = create_job(s)
        update_job(s, j2.id, status="failed")
        upsert_client_task(
            s,
            hash="h2",
            name="B",
            slug="slug",
            season=1,
            episode=2,
            language="German Dub",
            save_path=None,
            category=None,
            job_id=j2.id,
            state="downloading",
        )
        # cancelled
        j3 = create_job(s)
        update_job(s, j3.id, status="cancelled")
        upsert_client_task(
            s,
            hash="h3",
            name="C",
            slug="slug",
            season=1,
            episode=3,
            language="German Dub",
            save_path=None,
            category=None,
            job_id=j3.id,
            state="downloading",
        )

    data = client.get("/api/v2/sync/maindata").json()
    ts = data["torrents"]
    assert ts["h1"]["state"] == "uploading"
    assert ts["h2"]["state"] == "error"
    assert ts["h3"]["state"] == "pausedDL"
