"""One real Sonarr grab -> production AniBridge job -> generated-file import."""

import hashlib
import json
import sqlite3
import subprocess
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import TypeVar

import httpx

T = TypeVar("T")


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def wait(check: Callable[[], T], seconds: int) -> T:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = check()
        if result:
            return result
        time.sleep(2)
    raise TimeoutError("finite acceptance wait expired")


def fields(body: dict, values: dict) -> dict:
    for field in body["fields"]:
        if field["name"] in values:
            field["value"] = values[field["name"]]
    return body


def main() -> None:
    config = json.loads(Path("/config/client.json").read_text())
    assert config["source_id"] == "private-fixture", "fresh generated project required"
    assert Path("/generated/generated.mp4").is_file()
    assert not list(Path("/library").rglob("*.mkv")), "fresh library required"
    with httpx.Client(base_url="http://api:8000", trust_env=False, timeout=15) as api:

        def ready() -> bool:
            try:
                return api.get("/health", timeout=2).status_code == 200
            except httpx.HTTPError:
                return False

        wait(ready, 60)

        def jobs() -> list[dict]:
            response = api.get("/api/v2/torrents/info")
            response.raise_for_status()
            return response.json()

        assert jobs() == [], "do not run against existing grabs"
        # Existing client helper registers/tests both indexers and an unmonitored
        # TVDB 81189 descriptor. It never grabs and does not mutate job state.
        subprocess.run(
            ["python", "/pilot/clients.py", "--episode-search"],
            check=True,
            timeout=180,
        )
        key = ET.parse("/sonarr-config/config.xml").findtext("ApiKey")
        with httpx.Client(
            base_url="http://sonarr:8989/api/v3",
            headers={"X-Api-Key": key},
            trust_env=False,
            timeout=30,
        ) as sonarr:

            def call(
                method: str, path: str, body: dict | None = None, **params: object
            ) -> dict | list | None:
                response = sonarr.request(method, path, json=body, params=params)
                response.raise_for_status()
                return response.json() if response.content else None

            # Make Prowlarr part of the actual Sonarr search/grab chain, without
            # adding another sync/app setup or exposing either client's key.
            prowlarr_key = ET.parse("/prowlarr-config/config.xml").findtext("ApiKey")
            with httpx.Client(trust_env=False, timeout=15) as http:
                response = http.get(
                    "http://prowlarr:9696/api/v1/indexer",
                    headers={"X-Api-Key": prowlarr_key},
                )
                response.raise_for_status()
                indexers = response.json()
                assert len(indexers) == 1
            indexer = call("GET", "/indexer")[0]
            fields(
                indexer,
                {
                    "baseUrl": f"http://prowlarr:9696/{indexers[0]['id']}",
                    "apiPath": "/api",
                    "apiKey": prowlarr_key,
                },
            )
            call("POST", "/indexer/test", indexer)
            call("PUT", "/indexer/" + str(indexer["id"]), indexer)

            assert call("GET", "/downloadclient") == []
            template = next(
                row
                for row in call("GET", "/downloadclient/schema")
                if row["implementation"] == "QBittorrent"
            )
            fields(
                template,
                {
                    "host": "api",
                    "port": 8000,
                    "useSsl": False,
                    "urlBase": "",
                    "username": "",
                    "password": "",
                    "tvCategory": "acceptance",
                    "initialState": 0,
                },
            )
            template.update(
                name="Generated production-path acceptance",
                enable=True,
                priority=1,
                tags=[],
                removeCompletedDownloads=False,
            )
            call("POST", "/downloadclient/test", template)
            call("POST", "/downloadclient", template)
            settings = call("GET", "/config/downloadclient")
            settings["enableCompletedDownloadHandling"] = True
            call("PUT", "/config/downloadclient", settings)
            call("POST", "/rootfolder", {"path": "/library"})
            series = next(
                row for row in call("GET", "/series") if row["tvdbId"] == 81189
            )
            series.update(
                rootFolderPath="/library", path="/library/" + Path(series["path"]).name
            )
            call("PUT", "/series/" + str(series["id"]), series)
            episode = next(
                row
                for row in call("GET", "/episode", seriesId=series["id"])
                if row["seasonNumber"] == 1 and row["episodeNumber"] == 1
            )
            releases = call("GET", "/release", episodeId=episode["id"])
            release = next(row for row in releases if ".English.Sub" in row["title"])
            assert release["approved"] and release["quality"]["quality"]["id"] == 0
            # This is the sole grab. Sonarr calls the real qBittorrent add route;
            # only production Runner/Executor can create completion/output.
            call(
                "POST",
                "/release",
                {"guid": release["guid"], "indexerId": release["indexerId"]},
            )

            def completed() -> dict | None:
                rows = jobs()
                assert len(rows) <= 1
                if rows and rows[0]["state"] == "error":
                    raise RuntimeError(
                        "production job failed; retain state for diagnosis"
                    )
                return rows[0] if rows and rows[0]["progress"] == 1 else None

            row = wait(completed, 180)
            output = Path(row["content_path"])
            assert output.is_file() and output.is_relative_to(Path("/downloads"))
            assert output.with_name(".verified-output.json").is_file()
            output_digest = digest(output)
            with sqlite3.connect(
                "file:/data/anibridge_jobs.db?mode=ro", uri=True
            ) as db:
                record = db.execute(
                    "SELECT j.status,d.attempts FROM job j JOIN durable_request d ON j.id=d.job_id "
                    "JOIN clienttask c ON j.id=c.job_id WHERE c.hash=?",
                    (row["hash"],),
                ).fetchone()
                assert record == ("completed", 1)
            events = [
                json.loads(line)
                for line in Path("/data/acceptance-http-events.jsonl")
                .read_text()
                .splitlines()
            ]
            assert {event["input"] for event in events} >= {
                "provider",
                "player",
                "media",
            }
            assert all(event["process"] == "job_child.py" for event in events)

            command = call("POST", "/command", {"name": "RefreshMonitoredDownloads"})

            def refreshed() -> dict | None:
                record = call("GET", "/command/" + str(command["id"]))
                return record if record["status"] in {"completed", "failed"} else None

            assert wait(refreshed, 60)["status"] == "completed"

            def imported() -> dict | None:
                files = call("GET", "/episodefile", seriesId=series["id"])
                return next(
                    (
                        file
                        for file in files
                        if file["id"]
                        in {
                            row["episodeFileId"]
                            for row in call("GET", "/episode", seriesId=series["id"])
                            if row["id"] == episode["id"] and row["hasFile"]
                        }
                    ),
                    None,
                )

            file = wait(imported, 180)
            destination = Path(file["path"])
            assert destination.is_file() and destination.is_relative_to(
                Path("/library")
            )
            assert digest(destination) == output_digest
            probe = subprocess.run(
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-show_entries",
                    "stream=codec_type:format=duration",
                    "-of",
                    "json",
                    str(destination),
                ],
                capture_output=True,
                check=True,
                timeout=20,
            )
            inspected = json.loads(probe.stdout)
            assert float(inspected["format"]["duration"]) > 600
            assert {stream["codec_type"] for stream in inspected["streams"]} >= {
                "video",
                "audio",
            }
            result = {
                "acceptance": "passed",
                "job_status": "completed",
                "attempts": 1,
                "qbit_progress": 1,
                "imported_episode": "TVDB 81189 S01E01",
                "library_file": str(destination),
                "media": "generated test pattern/sine",
                "network": "fixture DNS/TLS/HTTP inputs; no live extraction proof",
            }
            Path("/data/acceptance-result.json").write_text(
                json.dumps(result, indent=2) + "\n"
            )
            print(json.dumps(result))


if __name__ == "__main__":
    main()
