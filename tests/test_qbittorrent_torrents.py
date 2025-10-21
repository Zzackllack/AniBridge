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
