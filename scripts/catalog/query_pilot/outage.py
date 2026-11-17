"""Exercise stale-cache handling only in the generated disposable fixture."""

import json
import os
import sqlite3
from collections.abc import Mapping
from pathlib import Path

import httpx


def require_fixture(environ: Mapping[str, str], config: Path) -> None:
    """Refuse production and real-provider rehearsals before opening their cache."""
    if environ.get("ANIBRIDGE_TEST_MODE", "").lower() not in {"1", "true"}:
        raise RuntimeError("outage probe requires the generated disposable fixture")
    if config.stat().st_size > 65536:
        raise RuntimeError("unexpected fixture configuration")
    worker = json.loads(config.read_bytes())
    if (
        worker.get("source_id") != "private-fixture"
        or not worker.get("providers")
        or set(worker["providers"].values()) != {"https://fixture.invalid"}
    ):
        raise RuntimeError("outage probe refuses non-fixture catalogs")


def main() -> None:
    require_fixture(os.environ, Path("/config/worker.json"))
    with sqlite3.connect("/data/catalog/query-cache.sqlite") as cache:
        cache.execute("UPDATE entry SET fetched=fetched-61")
    with httpx.Client(
        base_url="http://127.0.0.1:8000", trust_env=False, timeout=20
    ) as http:
        stale = http.get(
            "/torznab/api",
            params={"t": "tvsearch", "tvdbid": "81189", "season": "1", "limit": "100"},
        )
        assert (
            stale.status_code == 200
            and stale.headers["X-AniBridge-Catalog-Stale"] == "true"
        )
        cold = http.get("/torznab/api", params={"t": "tvsearch", "tvdbid": "987654321"})
        assert cold.status_code == 503 and b'code="900"' in cold.content
        assert http.get("/torznab/api", params={"t": "caps"}).status_code == 200
        jobs = http.get("/api/v2/torrents/info", params={"category": "pilot"}).json()
        assert jobs and all(job["state"] == "pausedDL" for job in jobs)
        print(
            json.dumps(
                {
                    "outage": "passed",
                    "stale_status": stale.status_code,
                    "stale_age_s": int(stale.headers["X-AniBridge-Catalog-Age"]),
                    "cold_status": cold.status_code,
                    "paused_jobs": len(jobs),
                    "clock": "cache fetch time advanced by SQL on disposable cache only",
                }
            )
        )


if __name__ == "__main__":
    main()
