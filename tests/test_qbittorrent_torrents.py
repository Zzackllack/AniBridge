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


def test_torrents_add_uses_cached_release_timestamp_for_added_on(client) -> None:
    """
    Verify that adding a torrent uses a cached release timestamp for the torrent's added_on field.

    Sets an availability record with a release_at timestamp, adds a torrent for that release, and asserts the torrent's `added_on` equals the integer Unix timestamp of the cached `release_at`.
    """
    from datetime import datetime, timezone
    from sqlmodel import Session

    from app.db import engine, upsert_availability
    from app.utils.magnet import build_magnet
    from app.utils.release_dates import RELEASE_AT_EXTRA_KEY

    release_at = datetime(2026, 2, 23, 19, 47, tzinfo=timezone.utc)
    with Session(engine) as s:
        upsert_availability(
            s,
            slug="release-slug",
            season=1,
            episode=1,
            language="German Dub",
            available=True,
            height=1080,
            vcodec="h264",
            provider="VOE",
            extra={RELEASE_AT_EXTRA_KEY: release_at.isoformat()},
            site="aniworld.to",
        )

    magnet = build_magnet(
        title="Title Release",
        slug="release-slug",
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
    assert items[0]["added_on"] == int(release_at.timestamp())
