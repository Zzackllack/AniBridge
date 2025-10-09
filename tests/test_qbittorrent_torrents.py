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


def test_torrents_add_records_absolute_metadata(client, monkeypatch):
    import app.api.qbittorrent.torrents as qb_torrents
    from app.utils.magnet import build_magnet

    captured: dict = {}

    def fake_schedule(req):
        captured["req"] = req
        return "job-abs"

    monkeypatch.setattr(qb_torrents, "schedule_download", fake_schedule)

    magnet = build_magnet(
        title="Absolute Test",
        slug="series-abs",
        season=2,
        episode=1,
        language="German Dub",
        absolute_number=5,
    )

    add = client.post("/api/v2/torrents/add", data={"urls": magnet})
    assert add.status_code == 200
    assert captured["req"]["absolute_number"] == 5

    info = client.get("/api/v2/torrents/info").json()
    assert len(info) == 1
    assert "[ABS 005]" in info[0]["name"]
    assert info[0]["anibridgeAbsolute"] == 5
