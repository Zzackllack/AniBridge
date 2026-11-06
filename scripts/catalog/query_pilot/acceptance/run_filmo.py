"""Run a real Radarr/Prowlarr grab through the durable Filmo job path."""

import argparse
from contextlib import closing
import hashlib
import json
import sqlite3
import subprocess
import time
import traceback
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urljoin, urlsplit
import httpx
from catalog_core import magnet
from filmo_fixture import IMDB_ID

MOVIE_ID = 10331
MOVIE_TITLE = "Night of the Living Dead"
MOVIE_YEAR = 1968
PILOT_INDEXER = "AniBridge Filmo generated acceptance"
PILOT_DOWNLOADER = "AniBridge authenticated qBittorrent adapter"
OUTPUT = Path("/data/acceptance-filmo-result.json")
AUTH = Path("/auth/qbit.json")
RADARR_IMPORT_MODE = "Move"


def wait[T](check: Callable[[], T], seconds: int, interval: float = 2) -> T:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(interval)
    raise TimeoutError("finite Filmo acceptance wait expired")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def probe_media(path: Path) -> dict:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height:stream_tags=language:format=duration,size",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        check=True,
        timeout=30,
    )
    return json.loads(result.stdout)


def streams_of_type(probe: dict, kind: str) -> list[dict]:
    return [stream for stream in probe["streams"] if stream["codec_type"] == kind]


def assert_embedded_tracks(probe: dict, *, remuxed: bool) -> dict:
    video = streams_of_type(probe, "video")
    audio = streams_of_type(probe, "audio")
    subtitles = streams_of_type(probe, "subtitle")
    assert len(video) == 1
    assert len(audio) == 2
    assert video[0]["codec_name"] == "h264"
    audio_languages = [stream.get("tags", {}).get("language") for stream in audio]
    assert all(stream["codec_name"] == "aac" for stream in audio)
    assert audio_languages == ["eng", "deu"]
    if remuxed:
        assert len(subtitles) == 1
        assert subtitles[0].get("tags", {}).get("language") == "deu"
        assert subtitles[0]["codec_name"] == "subrip"
    else:
        # The VTT enters through the Byse API route; the source MP4 has none.
        assert subtitles == []
    return {
        "video": {"codec": video[0]["codec_name"], "height": video[0]["height"]},
        "audio": [
            {
                "codec": stream["codec_name"],
                "language": stream.get("tags", {}).get("language"),
            }
            for stream in audio
        ],
        "subtitle": [
            {
                "codec": stream["codec_name"],
                "language": stream.get("tags", {}).get("language"),
            }
            for stream in subtitles
        ],
        "duration_s": float(probe["format"]["duration"]),
        "size_bytes": int(probe["format"]["size"]),
    }


def api_key(config: Path) -> str:
    key = ET.parse(config / "config.xml").findtext("ApiKey")
    if not key:
        raise RuntimeError("disposable client API key unavailable")
    return key


def wait_http(http: httpx.Client, path: str, seconds: int = 90) -> None:
    def ready() -> bool:
        try:
            return http.get(path, timeout=3).status_code == 200
        except httpx.HTTPError:
            return False

    wait(ready, seconds)


def set_fields(body: dict, values: dict[str, object]) -> None:
    fields = {field["name"]: field for field in body["fields"]}
    missing = values.keys() - fields.keys()
    if missing:
        raise AssertionError(f"client schema missing fields: {sorted(missing)}")
    for name, value in values.items():
        fields[name]["value"] = value


def get_json(http: httpx.Client, path: str, **params: object) -> object:
    response = http.get(path, params=params)
    response.raise_for_status()
    return response.json()


def request_json(
    http: httpx.Client, method: str, path: str, body: dict | None = None
) -> object:
    response = (
        http.request(method, path, json=body)
        if body is not None
        else http.request(method, path)
    )
    response.raise_for_status()
    return response.json() if response.content else None


def torznab_field_values(
    *, base_url: str, api_path: str, api_token: str, prowlarr: bool
) -> dict[str, object]:
    values: dict[str, object] = {
        "baseUrl": base_url,
        "apiPath": api_path,
        "apiKey": api_token,
    }
    # Prowlarr's Torznab schema does not expose categories; Radarr does.
    if not prowlarr:
        values["categories"] = [2000]
    return values


def add_torznab_indexer(
    http: httpx.Client,
    name: str,
    *,
    base_url: str,
    api_path: str,
    api_token: str,
    prowlarr: bool = False,
) -> dict:
    schema = next(
        row
        for row in get_json(http, "/indexer/schema")
        if row["implementation"] == "Torznab"
    )
    set_fields(
        schema,
        torznab_field_values(
            base_url=base_url,
            api_path=api_path,
            api_token=api_token,
            prowlarr=prowlarr,
        ),
    )
    schema.update(
        name=name,
        enableRss=True,
        enableAutomaticSearch=True,
        enableInteractiveSearch=True,
        priority=1,
        tags=[],
    )
    if prowlarr:
        schema.update(enable=True, appProfileId=1)
    test = http.post("/indexer/test", json=schema)
    if test.status_code not in (200, 202):
        raise RuntimeError(f"Torznab indexer test failed ({test.status_code})")
    created = request_json(http, "POST", "/indexer", schema)
    if not isinstance(created, dict) or not created.get("id"):
        raise RuntimeError("Torznab indexer registration failed")
    return created


def configure_pilot_indexers(
    prowlarr: httpx.Client, radarr: httpx.Client, prowlarr_key: str
) -> dict:
    prowlarr_indexer = add_torznab_indexer(
        prowlarr,
        PILOT_INDEXER,
        base_url="http://api:8000/torznab",
        api_path="/api",
        api_token="",
        prowlarr=True,
    )
    radarr_indexer = add_torznab_indexer(
        radarr,
        PILOT_INDEXER,
        base_url=f"http://prowlarr:9696/{prowlarr_indexer['id']}",
        api_path="/api",
        api_token=prowlarr_key,
    )
    return {"prowlarr": prowlarr_indexer, "radarr": radarr_indexer}


def configure_qbit_download_client(radarr: httpx.Client, auth: dict[str, str]) -> dict:
    if request_json(radarr, "GET", "/downloadclient"):
        raise AssertionError("fresh Radarr volume already has a download client")
    schema = next(
        row
        for row in get_json(radarr, "/downloadclient/schema")
        if row["implementation"] == "QBittorrent"
    )
    set_fields(
        schema,
        {
            "host": "api",
            "port": 8000,
            "useSsl": False,
            "urlBase": "",
            "username": auth["username"],
            "password": auth["password"],
            "movieCategory": "filmo-acceptance",
            "initialState": 0,
        },
    )
    schema.update(
        name=PILOT_DOWNLOADER,
        enable=True,
        priority=1,
        tags=[],
        removeCompletedDownloads=False,
        removeFailedDownloads=False,
    )
    test = radarr.post("/downloadclient/test", json=schema)
    if test.status_code not in (200, 202):
        raise RuntimeError(f"qBittorrent adapter test failed ({test.status_code})")
    created = request_json(radarr, "POST", "/downloadclient", schema)
    settings = get_json(radarr, "/config/downloadclient")
    settings["enableCompletedDownloadHandling"] = False
    request_json(radarr, "PUT", "/config/downloadclient", settings)
    if get_json(radarr, "/config/downloadclient")["enableCompletedDownloadHandling"]:
        raise AssertionError("Radarr completed-download handling must be disabled")
    return created


def add_movie(radarr: httpx.Client) -> dict:
    roots = get_json(radarr, "/rootfolder")
    if not any(root["path"] == "/library" for root in roots):
        request_json(radarr, "POST", "/rootfolder", {"path": "/library"})
    profiles = get_json(radarr, "/qualityprofile")
    if not profiles:
        raise RuntimeError("Radarr has no quality profile")
    profile_id = profiles[0]["id"]
    found = get_json(radarr, "/movie/lookup", term=f"tmdb:{MOVIE_ID}")
    movie = next(
        row for row in found if row["tmdbId"] == MOVIE_ID and row["year"] == MOVIE_YEAR
    )
    if movie["runtime"] <= 0:
        raise AssertionError("metadata lookup did not provide a runtime")
    existing = get_json(radarr, "/movie")
    if any(row["tmdbId"] == MOVIE_ID for row in existing):
        raise AssertionError("fresh Radarr volume already contains the pilot movie")
    movie.update(
        qualityProfileId=profile_id,
        rootFolderPath="/library",
        monitored=True,
        addOptions={"searchForMovie": False},
    )
    return request_json(radarr, "POST", "/movie", movie)


def import_completed_download(
    radarr: httpx.Client,
    movie_id: int,
    source: Path,
    download_id: str,
    *,
    timeout: int = 180,
) -> tuple[dict, dict]:
    command = request_json(
        radarr,
        "POST",
        "/command",
        {
            "name": "DownloadedMoviesScan",
            "path": str(source.parent),
            "downloadClientId": download_id.upper(),
            "importMode": RADARR_IMPORT_MODE,
        },
    )
    if not isinstance(command, dict) or type(command.get("id")) is not int:
        raise RuntimeError("Radarr did not queue the explicit movie import")

    def imported() -> tuple[dict, dict] | None:
        status = get_json(radarr, f"/command/{command['id']}")
        if not isinstance(status, dict):
            raise RuntimeError("Radarr returned invalid movie import status")
        if status.get("status") in {"failed", "aborted"}:
            raise RuntimeError("Radarr movie import command failed")
        if status.get("status") != "completed":
            return None
        movie = get_json(radarr, f"/movie/{movie_id}")
        if not isinstance(movie, dict) or not movie.get("hasFile"):
            return None
        files = get_json(radarr, "/moviefile", movieId=movie_id)
        if not isinstance(files, list):
            raise RuntimeError("Radarr returned invalid imported movie files")
        imported_file = next(
            (file for file in files if file.get("movieId") == movie_id), None
        )
        return (status, imported_file) if imported_file is not None else None

    return wait(imported, timeout)


def infohash(uri: str) -> str:
    digest_value, _payload, _label = magnet.decode(uri)
    return digest_value.lower()


def feed_magnet(value: str, *, link_origin: str | None) -> str:
    if value.startswith("magnet:?"):
        infohash(value)
        return value
    expected = urlsplit(link_origin or "")
    candidate = urlsplit(value)
    if (
        link_origin is None
        or expected.scheme != "http"
        or expected.netloc != "prowlarr:9696"
        or candidate.scheme != expected.scheme
        or candidate.netloc != expected.netloc
        or candidate.username
        or candidate.password
        or candidate.fragment
        or len(value.encode()) > 16384
    ):
        raise ValueError("unexpected non-magnet feed link")
    with httpx.Client(
        trust_env=False,
        follow_redirects=False,
        timeout=httpx.Timeout(10, connect=3, pool=1),
    ) as http:
        with http.stream("GET", value) as response:
            body_size = 0
            for chunk in response.iter_bytes(4096):
                body_size += len(chunk)
                if body_size > 65536:
                    raise ValueError("Prowlarr download response exceeded its bound")
            if response.status_code not in (301, 302):
                raise ValueError("Prowlarr download link did not redirect to a magnet")
            location = response.headers.get("location")
    if not location:
        raise ValueError("Prowlarr magnet redirect was empty")
    target = urljoin(value, location)
    if not target.startswith("magnet:?"):
        raise ValueError("Prowlarr download redirect was not a magnet")
    infohash(target)
    return target


def torznab_items(
    url: str, params: dict[str, str], *, link_origin: str | None = None
) -> list[dict[str, object]]:
    with httpx.Client(trust_env=False, timeout=25) as http:
        response = http.get(url, params=params)
        response.raise_for_status()
    root = ET.fromstring(response.content)
    items = []
    for item in root.findall("./channel/item"):
        attrs = {
            attr.attrib["name"]: attr.attrib["value"]
            for attr in item.findall("{*}attr")
        }
        magnet_uri = feed_magnet(
            attrs.get("magneturl", item.findtext("link") or ""),
            link_origin=link_origin,
        )
        items.append(
            {
                "title": item.findtext("title") or "",
                "guid": item.findtext("guid") or "",
                "magnet": magnet_uri,
                "attrs": attrs,
                "languages": [
                    node.attrib["value"]
                    for node in item.findall("{*}attr")
                    if node.attrib.get("name") == "language"
                ],
            }
        )
    return items


def parse_release(radarr: httpx.Client, title: str) -> dict:
    parsed = get_json(radarr, "/parse", title=title)
    if not isinstance(parsed, dict):
        raise AssertionError("Radarr parse endpoint returned an invalid result")
    languages = {
        language.get("name") if isinstance(language, dict) else language
        for language in parsed.get("languages", [])
    }
    if languages != {"English", "German"}:
        raise AssertionError("Radarr did not parse both declared audio languages")
    movie_info = parsed.get("parsedMovieInfo") or {}
    quality = movie_info.get("quality") or parsed.get("quality")
    if isinstance(quality, dict):
        quality = quality.get("quality", quality).get("name")
    if not isinstance(quality, str):
        raise AssertionError("Radarr parse response omitted its quality result")
    return parsed


def assert_radarr_quality(parsed: dict, source_id: str) -> None:
    movie_info = parsed.get("parsedMovieInfo") or {}
    quality = movie_info.get("quality") or parsed.get("quality") or {}
    if isinstance(quality, dict):
        quality = quality.get("quality", quality).get("name")
    if source_id == "84":
        if not isinstance(quality, str) or not all(
            token in quality.casefold() for token in ("bluray", "720p")
        ):
            raise AssertionError("Radarr did not parse variant 84 as BluRay 720p")
    elif source_id == "42":
        if quality != "Unknown":
            raise AssertionError("Radarr inferred a quality for generic WEB variant 42")
    else:
        raise AssertionError("Radarr parsed an undeclared fixture source variant")


def qbit_session() -> httpx.Client:
    auth = json.loads(AUTH.read_text())
    if set(auth) != {"username", "password"}:
        raise ValueError("qBittorrent fixture auth must contain username/password only")
    client = httpx.Client(base_url="http://api:8000", trust_env=False, timeout=20)
    response = client.post("/api/v2/auth/login", data=auth)
    if response.status_code != 200 or response.text.strip() != "Ok.":
        client.close()
        raise RuntimeError("qBittorrent fixture authentication failed")
    if "SID" not in client.cookies:
        client.close()
        raise RuntimeError("qBittorrent fixture session cookie was not issued")
    return client


def api_jobs(api: httpx.Client) -> list[dict]:
    response = api.get("/api/v2/torrents/info")
    response.raise_for_status()
    return response.json()


def initial_checks(api: httpx.Client) -> None:
    assert api_jobs(api) == [], "do not run against existing durable grabs"
    assert not list(Path("/downloads").glob("*")), "fresh downloads volume required"
    assert not list(Path("/library").glob("*")), "fresh movie library required"


def main() -> None:
    with httpx.Client(
        base_url="http://api:8000", trust_env=False, timeout=15
    ) as health:
        wait_http(health, "/health")

    prowlarr_key = api_key(Path("/prowlarr-config"))
    with httpx.Client(
        base_url="http://prowlarr:9696/api/v1",
        headers={"X-Api-Key": prowlarr_key},
        trust_env=False,
        timeout=30,
    ) as prowlarr_http:
        wait_http(prowlarr_http, "/system/status")
        assert get_json(prowlarr_http, "/indexer") == []
        radarr_key = api_key(Path("/radarr-config"))
        with httpx.Client(
            base_url="http://radarr:7878/api/v3",
            headers={"X-Api-Key": radarr_key},
            trust_env=False,
            timeout=30,
        ) as radarr_http:
            wait_http(radarr_http, "/system/status")
            assert get_json(radarr_http, "/indexer") == []
            assert get_json(radarr_http, "/movie") == []
            auth = json.loads(AUTH.read_text())
            with closing(qbit_session()) as api:
                initial_checks(api)
                clients = configure_pilot_indexers(
                    prowlarr_http, radarr_http, prowlarr_key
                )
                qbit = configure_qbit_download_client(radarr_http, auth)
                assert qbit["name"] == PILOT_DOWNLOADER
                movie = add_movie(radarr_http)
                assert movie["tmdbId"] == MOVIE_ID
                assert movie["imdbId"] == IMDB_ID
                generated_tracks = assert_embedded_tracks(
                    probe_media(Path("/generated/generated.mp4")), remuxed=False
                )
                assert generated_tracks["duration_s"] == 6001
                assert generated_tracks["size_bytes"] <= 64 * 1024**2
                assert generated_tracks["subtitle"] == []
                assert generated_tracks["duration_s"] > movie["runtime"] * 60

                direct_items = torznab_items(
                    "http://api:8000/torznab/api",
                    {
                        "t": "movie",
                        "tmdbid": str(MOVIE_ID),
                        "imdbid": IMDB_ID,
                        "limit": "20",
                    },
                )
                items = torznab_items(
                    f"http://prowlarr:9696/{clients['prowlarr']['id']}/api",
                    {
                        "apikey": prowlarr_key,
                        "t": "movie",
                        "tmdbid": str(MOVIE_ID),
                        "imdbid": IMDB_ID,
                        "limit": "20",
                    },
                    link_origin="http://prowlarr:9696",
                )
                assert len(direct_items) == len(items) == 2, (
                    "expected exactly two generated Filmo variants through API and Prowlarr"
                )
                assert {infohash(item["magnet"]) for item in direct_items} == {
                    infohash(item["magnet"]) for item in items
                }, "Prowlarr changed the frozen source variant hashes"
                assert {
                    item["attrs"].get("anibridge_source_id") for item in direct_items
                } == {
                    "42",
                    "84",
                }
                assert {
                    item["attrs"]["anibridge_source_id"]: item["attrs"].get(
                        "anibridge_source_claim"
                    )
                    for item in direct_items
                } == {"42": "web", "84": "bluray"}
                assert all(
                    set(item["languages"]) == {"English", "German"}
                    for item in direct_items
                )
                assert all(
                    item["attrs"].get("anibridge_audio_languages") == "deu,eng"
                    and "anibridge_subtitle_languages" not in item["attrs"]
                    for item in direct_items
                )
                hashes = {infohash(item["magnet"]) for item in direct_items}
                assert len(hashes) == 2

                for item in direct_items:
                    _hash, payload, _label = magnet.decode(item["magnet"])
                    assert payload["provider"] == "filmo.to"
                    assert (
                        payload["release_metadata"]["native_id"]
                        == item["attrs"]["anibridge_source_id"]
                    )
                    parsed = parse_release(radarr_http, item["title"])
                    assert parsed["parsedMovieInfo"]["year"] == MOVIE_YEAR
                    assert_radarr_quality(parsed, item["attrs"]["anibridge_source_id"])

                releases = get_json(radarr_http, "/release", movieId=movie["id"])
                assert len(releases) == 2
                release = next(
                    row
                    for row in releases
                    if "BluRay" in row["title"] or "Bluray" in row["title"]
                )
                assert release["downloadAllowed"] and not release["rejected"]
                selected_torrent = next(
                    item
                    for item in direct_items
                    if "BluRay" in item["title"] or "Bluray" in item["title"]
                )
                selected_hash = infohash(selected_torrent["magnet"])
                assert selected_hash in hashes

                grabbed = request_json(
                    radarr_http,
                    "POST",
                    "/release",
                    {"guid": release["guid"], "indexerId": release["indexerId"]},
                )
                assert grabbed is not None

                def admitted() -> dict | None:
                    rows = api_jobs(api)
                    assert len(rows) <= 1
                    matching = next(
                        (row for row in rows if row["hash"].lower() == selected_hash),
                        None,
                    )
                    if rows and not matching:
                        raise AssertionError("Radarr grabbed an unexpected variant")
                    return matching

                row = wait(admitted, 90)
                with closing(
                    sqlite3.connect("file:/data/anibridge_jobs.db?mode=ro", uri=True)
                ) as db:
                    durable = db.execute(
                        "SELECT j.id,j.status,d.attempts,d.payload FROM job j "
                        "JOIN durable_request d ON d.job_id=j.id "
                        "JOIN clienttask c ON c.job_id=j.id WHERE c.hash=?",
                        (selected_hash,),
                    ).fetchone()
                assert durable is not None
                job_id, _status, _attempts, payload_text = durable
                frozen = json.loads(payload_text)
                assert frozen["provider"] == "filmo.to"
                assert frozen["release_metadata"]["native_id"] == "84"
                assert frozen["release_metadata"]["quality"]["source"] == "bluray"
                assert frozen["release_metadata"]["audio_languages"] == [
                    "deu",
                    "eng",
                ]
                assert frozen["release_metadata"]["subtitle_languages"] is None

                intermediate_api = []
                intermediate_radarr = []

                def completed() -> dict | None:
                    torrent = next(
                        row
                        for row in api_jobs(api)
                        if row["hash"].lower() == selected_hash
                    )
                    if torrent["state"] == "error":
                        raise RuntimeError("durable Filmo job failed")
                    if 0 < torrent["progress"] < 1:
                        intermediate_api.append(
                            {
                                key: torrent[key]
                                for key in ("progress", "size", "downloaded")
                            }
                        )
                        assert torrent["size"] > 0
                        assert 0 < torrent["downloaded"] <= torrent["size"]
                        queue = get_json(radarr_http, "/queue", page=1, pageSize=100)
                        for queued in queue["records"]:
                            if (
                                str(queued.get("downloadId", "")).lower()
                                == selected_hash
                            ):
                                size, left = queued["size"], queued["sizeleft"]
                                if size > 0 and 0 < left < size:
                                    intermediate_radarr.append(
                                        {
                                            "size": size,
                                            "sizeleft": left,
                                            "status": queued["status"],
                                        }
                                    )
                    return torrent if torrent["progress"] == 1 else None

                row = wait(completed, 420)
                assert intermediate_api, (
                    "no intermediate AniBridge byte progress observed"
                )
                assert intermediate_radarr, (
                    "no intermediate Radarr byte progress observed"
                )
                source = Path(row["content_path"])
                assert source.is_file() and source.is_relative_to(Path("/downloads"))
                output_digest = digest(source)
                output_size = source.stat().st_size
                receipt = json.loads(
                    source.with_name(".verified-output.json").read_text()
                )
                assert receipt["sha256"] == output_digest
                assert receipt["size"] == output_size

                scan_status, imported_file = import_completed_download(
                    radarr_http,
                    movie["id"],
                    source,
                    selected_hash,
                )
                destination = Path(imported_file["path"])
                assert destination.is_relative_to(Path("/library"))
                assert destination.is_file() and digest(destination) == output_digest
                assert not source.exists(), (
                    "Radarr Move import should remove the source"
                )
                moved = next(
                    row for row in api_jobs(api) if row["hash"].lower() == selected_hash
                )
                assert moved["progress"] == 1
                assert moved["state"] == "missingFiles"
                assert moved["content_path"] == ""
                assert moved["anibridge_output_missing"] is True
                inspected = probe_media(destination)
                imported_tracks = assert_embedded_tracks(inspected, remuxed=True)
                duration = imported_tracks["duration_s"]
                assert abs(duration - generated_tracks["duration_s"]) <= 0.1
                assert duration > movie["runtime"] * 60
                with closing(
                    sqlite3.connect("file:/data/anibridge_jobs.db?mode=ro", uri=True)
                ) as db:
                    status = db.execute(
                        "SELECT j.status,d.attempts,count(c.hash),j.downloaded_bytes,j.total_bytes FROM job j "
                        "JOIN durable_request d ON d.job_id=j.id "
                        "JOIN clienttask c ON c.job_id=j.id WHERE j.id=? GROUP BY j.id",
                        (job_id,),
                    ).fetchone()
                assert status == ("completed", 1, 1, output_size, output_size)
                events = [
                    json.loads(line)
                    for line in Path("/data/filmo-acceptance-http-events.jsonl")
                    .read_text()
                    .splitlines()
                ]
                stages = {event["input"] for event in events}
                assert sum(event["input"] == "caption" for event in events) == 1
                assert {
                    "detail",
                    "mint",
                    "wrapper_alternate",
                    "byse_embed_alternate",
                    "byse_api",
                    "caption",
                    "media",
                } <= stages
                assert not {
                    "wrapper_primary",
                    "byse_embed_primary",
                }.intersection(stages), "resolver touched the other queued variant"
                assert all(event["process"] == "job_child.py" for event in events)

                result = {
                    "acceptance": "passed",
                    "provider": "filmo.to",
                    "movie": {
                        "tmdb_id": MOVIE_ID,
                        "title": MOVIE_TITLE,
                        "year": MOVIE_YEAR,
                    },
                    "source_variants": sorted(
                        item["attrs"]["anibridge_source_id"] for item in direct_items
                    ),
                    "selected_native_id": frozen["release_metadata"]["native_id"],
                    "selected_hash": selected_hash,
                    "quality": frozen["release_metadata"]["quality"],
                    "audio_languages": frozen["release_metadata"]["audio_languages"],
                    "subtitle_languages": frozen["release_metadata"][
                        "subtitle_languages"
                    ],
                    "external_caption": {
                        "language": "deu",
                        "source_format": "vtt",
                        "remux_format": imported_tracks["subtitle"][0]["codec"],
                    },
                    "job_status": status[0],
                    "attempts": status[1],
                    "library_file": str(destination),
                    "sha256": output_digest,
                    "generated_duration_s": duration,
                    "metadata_runtime_s": movie["runtime"] * 60,
                    "embedded_tracks": imported_tracks,
                    "post_import_state": moved["state"],
                    "post_import_output_missing": moved["anibridge_output_missing"],
                    "import_mode": RADARR_IMPORT_MODE,
                    "automatic_handling_disabled": True,
                    "radarr_import_command": {
                        "id": scan_status["id"],
                        "status": scan_status["status"],
                        "result": scan_status.get("result"),
                    },
                    "intermediate_api": intermediate_api,
                    "intermediate_radarr": intermediate_radarr,
                    "fixture_stages": sorted(stages),
                    "network": "fixture Filmo/provider/player/media inputs; no real media acquisition",
                    "restart": "not_checked",
                }
                OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
                print(json.dumps(result))


def verify_restart() -> None:
    result = json.loads(OUTPUT.read_text())
    assert result["acceptance"] == "passed"
    destination = Path(result["library_file"])
    assert destination.is_file() and digest(destination) == result["sha256"]
    with httpx.Client(base_url="http://api:8000", trust_env=False, timeout=10) as api:
        wait_http(api, "/health", seconds=20)
        auth = json.loads(AUTH.read_text())
        response = api.post("/api/v2/auth/login", data=auth)
        assert response.status_code == 200 and response.text.strip() == "Ok."

        def stable_for_window() -> dict:
            deadline = time.monotonic() + 30
            latest = None
            while time.monotonic() < deadline:
                response = api.get("/api/v2/torrents/info")
                response.raise_for_status()
                rows = response.json()
                assert (
                    len(rows) == 1
                    and rows[0]["hash"].lower() == result["selected_hash"]
                )
                latest = rows[0]
                assert latest["progress"] == 1
                assert latest["state"] == "missingFiles"
                assert latest["content_path"] == ""
                assert latest["anibridge_output_missing"] is True
                with closing(
                    sqlite3.connect("file:/data/anibridge_jobs.db?mode=ro", uri=True)
                ) as db:
                    assert db.execute(
                        "SELECT j.status,d.attempts,count(c.hash) FROM job j "
                        "JOIN durable_request d ON d.job_id=j.id "
                        "JOIN clienttask c ON c.job_id=j.id GROUP BY j.id"
                    ).fetchall() == [("completed", 1, 1)]
                time.sleep(2)
            assert latest is not None
            return latest

        row = stable_for_window()
        result["restart"] = {
            "passed": True,
            "attempts": 1,
            "state": row["state"],
            "window_s": 30,
        }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-restart", action="store_true")
    args = parser.parse_args()
    try:
        verify_restart() if args.verify_restart else main()
    except Exception as error:  # noqa: BLE001 -- HTTP exception strings can expose client API keys
        frames = [
            frame
            for frame in traceback.extract_tb(error.__traceback__)
            if frame.filename == __file__
        ]
        failed = {
            "outcome": "failed",
            "error_class": type(error).__name__,
            "line": frames[-1].lineno if frames else None,
            "runner_frames": [frame.lineno for frame in frames],
        }
        if isinstance(error, httpx.HTTPStatusError):
            failed["http_status"] = error.response.status_code
        print(json.dumps(failed))
        raise SystemExit(1) from None
