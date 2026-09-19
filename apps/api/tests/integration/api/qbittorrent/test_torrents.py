def test_torrent_lifecycle(client):
    from app.utils.magnet import build_magnet

    resp = client.post(
        "/api/v2/torrents/createCategory",
        data={"category": "anime", "savePath": "/tmp"},
    )
    assert resp.status_code == 200

    magnet = build_magnet(
        title="Title",
        slug="slug",
        season=1,
        episode=1,
        language="German Dub",
    )
    add = client.post(
        "/api/v2/torrents/add", data={"urls": magnet, "category": "anime"}
    )
    assert add.status_code == 200

    info = client.get("/api/v2/torrents/info")
    items = info.json()
    assert len(items) == 1
    assert items[0]["state"] == "downloading"
    h = items[0]["hash"]

    del_resp = client.post("/api/v2/torrents/delete", data={"hashes": h})
    assert del_resp.status_code == 200

    info2 = client.get("/api/v2/torrents/info")
    assert info2.json() == []


def test_torrents_add_aw_and_sto_prefixes(client):
    """
    Test adding two torrents built with aw- and sto- prefixed magnets and verifies both are present.

    Builds two magnet links (one using default site, one with site "s.to"), posts them to /api/v2/torrents/add with category "anime", asserts both add requests return HTTP 200, and asserts that /api/v2/torrents/info reports exactly two items.
    """
    from app.utils.magnet import build_magnet

    # Add torrent with aw prefix
    magnet_aw = build_magnet(
        title="Title AW",
        slug="aw-slug",
        season=1,
        episode=1,
        language="German Dub",
    )
    add_aw = client.post(
        "/api/v2/torrents/add", data={"urls": magnet_aw, "category": "anime"}
    )
    assert add_aw.status_code == 200

    # Add torrent with sto prefix
    magnet_sto = build_magnet(
        title="Title STO",
        slug="sto-slug",
        season=1,
        episode=1,
        language="German Dub",
        site="s.to",
    )
    add_sto = client.post(
        "/api/v2/torrents/add", data={"urls": magnet_sto, "category": "anime"}
    )
    assert add_sto.status_code == 200

    # Check that both are added
    info = client.get("/api/v2/torrents/info")
    items = info.json()
    assert len(items) == 2


def test_torrents_add_starts_worker_after_task_write(client, monkeypatch):
    from app.utils.magnet import build_magnet
    import app.api.qbittorrent.torrents as qb_torrents

    calls: list[tuple[str, str]] = []

    def _schedule_download(req, *, autostart=True):
        del req
        calls.append(("schedule", "autostart" if autostart else "deferred"))
        return "job-1"

    monkeypatch.setattr(
        qb_torrents,
        "schedule_download",
        _schedule_download,
    )
    monkeypatch.setattr(
        qb_torrents,
        "start_scheduled_job",
        lambda job_id, req: calls.append(("start", job_id)),
    )

    magnet = build_magnet(
        title="Title",
        slug="slug",
        season=1,
        episode=1,
        language="German Dub",
    )
    response = client.post("/api/v2/torrents/add", data={"urls": magnet})

    assert response.status_code == 200
    assert calls == [("schedule", "deferred"), ("start", "job-1")]


def test_torrents_info_preserves_queued_state_for_paused_add(client):
    from app.utils.magnet import build_magnet

    magnet = build_magnet(
        title="Queued Title",
        slug="queued-title",
        season=1,
        episode=1,
        language="German Dub",
    )

    response = client.post(
        "/api/v2/torrents/add", data={"urls": magnet, "paused": "true"}
    )

    assert response.status_code == 200

    info = client.get("/api/v2/torrents/info").json()
    assert info[0]["state"] == "queuedDL"


def test_torrents_resume_starts_paused_job_with_original_request(client, monkeypatch):
    from app.utils.magnet import build_magnet
    import app.api.qbittorrent.torrents as qb_torrents
    from app.db import create_job, engine
    from sqlmodel import Session

    started: list[tuple[str, dict]] = []

    def create_queued_job(req, *, autostart=True):
        del autostart
        with Session(engine) as session:
            return create_job(session, source_site=req["site"]).id

    monkeypatch.setattr(qb_torrents, "schedule_download", create_queued_job)
    monkeypatch.setattr(
        qb_torrents,
        "start_scheduled_job",
        lambda job_id, req: started.append((job_id, req)),
    )
    magnet = build_magnet(
        title="Queued STRM",
        slug="queued-strm",
        season=2,
        episode=3,
        language="German Dub",
        provider="VOE",
        mode="strm",
    )

    add_response = client.post(
        "/api/v2/torrents/add",
        data={"urls": magnet, "paused": "true"},
    )
    torrent_hash = client.get("/api/v2/torrents/info").json()[0]["hash"]
    resume_response = client.post(
        "/api/v2/torrents/resume",
        data={"hashes": torrent_hash},
    )

    assert add_response.status_code == 200
    assert resume_response.status_code == 200
    assert len(started) == 1
    assert started[0][1] == {
        "slug": "queued-strm",
        "season": 2,
        "episode": 3,
        "language": "German Dub",
        "site": "aniworld.to",
        "title_hint": "Queued STRM",
        "provider": "VOE",
        "mode": "strm",
    }
    info = client.get("/api/v2/torrents/info").json()
    assert info[0]["state"] == "downloading"


def test_torrents_add_returns_500_when_start_fails(client, monkeypatch):
    from app.utils.magnet import build_magnet
    import app.api.qbittorrent.torrents as qb_torrents

    monkeypatch.setattr(
        qb_torrents,
        "start_scheduled_job",
        lambda job_id, req: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    magnet = build_magnet(
        title="Title",
        slug="slug",
        season=1,
        episode=1,
        language="German Dub",
    )
    response = client.post("/api/v2/torrents/add", data={"urls": magnet})

    assert response.status_code == 500

    info = client.get("/api/v2/torrents/info").json()
    assert info[0]["state"] == "error"
