"""Run inside the disposable API container; accept one paused synthetic grab."""

import json
import sqlite3
import time
import xml.etree.ElementTree as ET

import httpx

with httpx.Client(
    base_url="http://127.0.0.1:8000", trust_env=False, timeout=20
) as http:
    for _ in range(30):
        try:
            if http.get("/health").status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    caps = http.get("/torznab/api", params={"t": "caps"})
    assert caps.status_code == 200
    params = {"t": "tvsearch", "tvdbid": "81189", "season": "1", "limit": "100"}
    result = http.get("/torznab/api", params=params)
    assert result.status_code == 200, result.text
    feed = ET.fromstring(result.content)
    items = feed.findall("./channel/item")
    assert len(items) == 40
    assert all("720p" not in item.findtext("title") for item in items)
    repeated = http.get("/torznab/api", params=params)
    assert repeated.content == result.content
    grab = items[0].findtext("link")
    accepted = http.post(
        "/api/v2/torrents/add",
        data={"urls": grab, "paused": "true", "category": "pilot"},
    )
    assert accepted.status_code == 200, accepted.text
    tasks = http.get("/api/v2/torrents/info", params={"category": "pilot"}).json()
    assert tasks and all(row["state"] == "pausedDL" for row in tasks)
    with sqlite3.connect("/data/anibridge_jobs.db") as db:
        payload = json.loads(
            db.execute("SELECT payload FROM durable_request LIMIT 1").fetchone()[0]
        )
        assert payload["catalog_source"]["source_id"] == "private-fixture"
        assert payload["provider"] == "aniworld.to" and payload["native_season"] == 1
    recent = http.get(
        "/torznab/api", params={"t": "search", "limit": "2", "offset": "1"}
    )
    assert (
        recent.status_code == 200
        and len(ET.fromstring(recent.content).findall("./channel/item")) == 2
    )
    print(
        json.dumps(
            {
                "smoke": "passed",
                "season_releases": len(items),
                "paused_jobs": len(tasks),
                "rss_bytes": len(result.content),
            }
        )
    )
