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
