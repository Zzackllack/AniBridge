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
