"""Actual disposable Sonarr/Prowlarr indexer tests; no grab/download is issued."""

import argparse
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--tvdb-id", type=int, default=81189)
parser.add_argument("--season", type=int, default=1)
parser.add_argument("--episode", type=int, default=1)
parser.add_argument("--expected-season-releases", type=int, default=40)
parser.add_argument("--expected-episode-releases", type=int, default=2)
parser.add_argument("--episode-search", action="store_true")
parser.add_argument("--season-search", action="store_true")
args = parser.parse_args()
if not (args.tvdb_id > 0 and args.season > 0 and args.episode > 0):
    parser.error("positive selected TVDB ID/season/episode required")
if not (
    1 <= args.expected_season_releases <= 100
    and 1 <= args.expected_episode_releases <= 100
):
    parser.error("explicit expected release counts must be between 1 and 100")


def api_key(directory: Path) -> str:
    end = time.monotonic() + 60
    while time.monotonic() < end:
        path = directory / "config.xml"
        if path.exists():
            key = ET.parse(path).findtext("ApiKey")
            if key:
                return key
        time.sleep(1)
    raise TimeoutError("disposable client config startup")


def configure(base: str, directory: Path, version: str) -> dict:
    key = api_key(directory)
    with httpx.Client(
        base_url=base + version, headers={"X-Api-Key": key}, trust_env=False, timeout=20
    ) as http:
        end = time.monotonic() + 60
        while time.monotonic() < end:
            try:
                response = http.get("/system/status")
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(1)
        else:
            raise TimeoutError("disposable client API startup")
        status = response.json()
        schema = http.get("/indexer/schema")
        schema.raise_for_status()
        indexer = next(
            item for item in schema.json() if item["implementation"] == "Torznab"
        )
        values = {
            "baseUrl": "http://api:8000/torznab"
            if version == "/api/v1"
            else "http://api:8000",
            "apiPath": "/api" if version == "/api/v1" else "/torznab/api",
            "apiKey": "",
            "categories": [5070, 5000],
        }
        for field in indexer["fields"]:
            if field["name"] in values:
                field["value"] = values[field["name"]]
        indexer.update(name="Request API discovery pilot", priority=25, tags=[])
        if version == "/api/v1":
            indexer.update(enable=True, appProfileId=1)
        else:
            indexer.update(
                enableRss=True, enableAutomaticSearch=True, enableInteractiveSearch=True
            )
        existing = http.get("/indexer").json()
        registered = next(
            (
                item
                for item in existing
                if item["name"] == "Request API discovery pilot"
            ),
            None,
        )
        if registered is not None:
            indexer["id"] = registered["id"]
        test = http.post("/indexer/test", json=indexer)
        assert test.status_code in {200, 202}, (test.status_code, test.text[:300])
        if registered is None:
            registered = http.post("/indexer", json=indexer)
            registered.raise_for_status()
            registered = registered.json()
        return {
            "version": status["version"],
            "indexer_test_status": test.status_code,
            "registered_indexer_id": registered["id"],
            "implementation": indexer["implementation"],
        }


# Client apps can start before AniBridge has finished its DB lifecycle startup.
with httpx.Client(trust_env=False, timeout=2) as health:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            if health.get("http://api:8000/health").status_code == 200:
                break
        except httpx.HTTPError:
            pass
        time.sleep(1)
    else:
        raise TimeoutError("local AniBridge startup")

sonarr = configure("http://sonarr:8989", Path("/sonarr-config"), "/api/v3")
prowlarr = configure("http://prowlarr:9696", Path("/prowlarr-config"), "/api/v1")
# Prowlarr forwards the actual explicit TVDB/season request to AniBridge.
key = api_key(Path("/prowlarr-config"))
with httpx.Client(trust_env=False, timeout=20) as http:
    response = http.get(
        f"http://prowlarr:9696/{prowlarr['registered_indexer_id']}/api",
        params={
            "apikey": key,
            "t": "tvsearch",
            "tvdbid": str(args.tvdb_id),
            "season": str(args.season),
            "limit": "100",
        },
    )
    response.raise_for_status()
    items = ET.fromstring(response.content).findall("./channel/item")
    assert len(items) == args.expected_season_releases
    assert all("720p" not in item.findtext("title") for item in items)
print(
    json.dumps(
        {
            "sonarr": sonarr,
            "prowlarr": prowlarr,
            "forwarded_season_releases": len(items),
            "tvdb_id": args.tvdb_id,
            "season": args.season,
            "proof": "real-client indexer tests and season forwarding; no grab, import or playback",
        }
    )
)

# Optional one public descriptor lookup, then an actual Sonarr episode search.
# No monitored library, release POST, provider fetch or video download is created.
if args.episode_search or args.season_search:
    with httpx.Client(
        base_url="http://sonarr:8989/api/v3",
        headers={"X-Api-Key": api_key(Path("/sonarr-config"))},
        trust_env=False,
        timeout=30,
    ) as http:
        profiles = http.get("/qualityprofile").json()
        profile = next(
            (p for p in profiles if p["name"] == "Request API Unknown"), None
        )
        if profile is None:
            profile = http.get("/qualityprofile/schema").json()
            profile.update(name="Request API Unknown", upgradeAllowed=False, cutoff=0)
            for item in profile["items"]:
                item["allowed"] = item.get("quality", {}).get("id") == 0
            response = http.post("/qualityprofile", json=profile)
            response.raise_for_status()
            profile = response.json()
        Path("/downloads/library").mkdir(exist_ok=True)
        roots = http.get("/rootfolder").json()
        if not any(root["path"] == "/downloads/library" for root in roots):
            response = http.post("/rootfolder", json={"path": "/downloads/library"})
            response.raise_for_status()
        series = next(
            (s for s in http.get("/series").json() if s["tvdbId"] == args.tvdb_id), None
        )
        if series is None:
            response = http.get(
                "/series/lookup", params={"term": f"tvdb:{args.tvdb_id}"}
            )
            response.raise_for_status()
            selected = [row for row in response.json() if row["tvdbId"] == args.tvdb_id]
            assert len(selected) == 1
            series = selected[0]
            series.update(
                qualityProfileId=profile["id"],
                rootFolderPath="/downloads/library",
                monitored=False,
                seasonFolder=True,
                addOptions={"searchForMissingEpisodes": False, "monitor": "none"},
            )
            response = http.post("/series", json=series)
            response.raise_for_status()
            series = response.json()
        assert series["monitored"] is False
        end = time.monotonic() + 45
        while time.monotonic() < end:
            episodes = http.get("/episode", params={"seriesId": series["id"]}).json()
            episode = next(
                (
                    e
                    for e in episodes
                    if e["seasonNumber"] == args.season
                    and e["episodeNumber"] == args.episode
                ),
                None,
            )
            if episode:
                break
            time.sleep(1)
        assert episode is not None and all(e["monitored"] is False for e in episodes)
        response = http.get("/release", params={"episodeId": episode["id"]})
        response.raise_for_status()
        releases = response.json()
        assert len(releases) == args.expected_episode_releases
        assert all(release["quality"]["quality"]["id"] == 0 for release in releases)
        print(
            json.dumps(
                {
                    "sonarr_episode_search": "passed",
                    "releases": len(releases),
                    "quality": "Unknown",
                    "monitored": False,
                    "grab": False,
                    "public_descriptor_lookup": f"TVDB {args.tvdb_id} via Sonarr lookup only",
                    "season": args.season,
                    "episode": args.episode,
                }
            )
        )

        if args.season_search:
            response = http.get(
                "/release",
                params={"seriesId": series["id"], "seasonNumber": args.season},
            )
            response.raise_for_status()
            releases = response.json()
            assert len(releases) == args.expected_season_releases
            assert all(release["quality"]["quality"]["id"] == 0 for release in releases)
            # Sonarr reports discovery identity in mappedSeriesId; seriesId is
            # reserved for manually queued unknown releases and may be absent.
            assert all(
                release["mappedSeriesId"] == series["id"] for release in releases
            )
            assert all(
                release["mappedSeasonNumber"] == args.season for release in releases
            )
            assert all(
                release["mappedEpisodeNumbers"] == release["episodeNumbers"]
                for release in releases
            )
            assert all(release["rejected"] is False for release in releases)
            print(
                json.dumps(
                    {
                        "sonarr_season_search": "passed",
                        "matched_episode_numbers": sorted(
                            {n for r in releases for n in r["mappedEpisodeNumbers"]}
                        ),
                        "tvdb_id": args.tvdb_id,
                        "season": args.season,
                        "releases": len(releases),
                        "quality": "Unknown",
                        "monitored": False,
                        "grab": False,
                    }
                )
            )
