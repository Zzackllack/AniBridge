"""Bounded publication A/B on marked consistent copies, with networking disabled.

Seed with the new worker, then run legacy full publication and new incremental
publication on the exact same generated metadata edits. Legacy uses only State's
read/export methods against the unchanged public ledger tables: its v5 startup
cannot open v6 bookkeeping. Source preflight is reported separately, not hidden
inside an engine/publication comparison. Never use this harness on live state.
"""

import argparse
import asyncio
import json
import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import patch

import httpx
from catalog_core import diagnostics, schema
from catalog_core.protocol import Request
from catalog_worker.config import Config, load
from catalog_worker.query_server import create_app
from catalog_worker.read_catalog import provider_root, publish
from catalog_worker.state import State
from mapping_replay import metrics, resources

PROVIDERS = ("aniworld.to", "s.to")


def configuration(root: Path, state: Path, label: str) -> Config:
    path = root / (label + ".json")
    path.write_text(
        json.dumps(
            {
                "providers": {
                    "aniworld.to": "https://aniworld.to",
                    "s.to": "https://serienstream.to",
                },
                "canonical_sources": {"tv": "off", "movie": "off"},
                "publication_sources": ["skyhook-v1", "tmdb-v3"],
                "state_dir": str(state),
                "output_dir": str(root / label),
                "source_id": "publication-benchmark",
                "limits": {"publish_interval_s": 300},
            }
        )
    )
    return load(path)


def one(
    config: Config,
    provider: str,
    now: int,
    legacy: bool,
    ready: threading.Event | None = None,
    *,
    full: bool = False,
) -> dict:
    filename = config.state_dir / (provider + ".sqlite")
    begin = time.monotonic()
    if legacy:
        # Public projections are v1/v2-compatible. No old migration or writer is
        # run against new private tables; only copied publication fields change.
        state = State.__new__(State)
        state.db = sqlite3.connect(filename)
        state.db.row_factory = sqlite3.Row
        state.provider = provider
    else:
        state = State(filename, provider)
    preflight_s = time.monotonic() - begin
    try:
        diagnostics._records.clear()
        before = resources()
        start = time.monotonic()
        if ready is not None:
            ready.set()
        metadata = (
            publish(config, state, now)
            if legacy
            else publish(config, state, now, full=full)
        )
        elapsed = time.monotonic() - start
        return {
            "preflight_s": round(preflight_s, 4),
            "publication_s": round(elapsed, 4),
            "phases": list(diagnostics._records),
            "resources_before": before,
            "resources_after": resources(),
            "counts": metadata["counts"],
            "revision": metadata["revision"],
        }
    finally:
        state.close()


def seed(config: Config, now: int) -> dict:
    result = {}
    for provider in PROVIDERS:
        first = one(config, provider, now, False, full=True)
        state = State(config.state_dir / (provider + ".sqlite"), provider)
        try:
            # Two deterministic title partitions: ordinary and large. These
            # generated names are workload fixtures, not live-provider evidence.
            rows = state.db.execute(
                "SELECT title_id,count(*) AS n FROM entity WHERE kind='episode' GROUP BY title_id"
            ).fetchall()
            ordinary = min((r for r in rows if 5 <= r[1] <= 50), key=lambda r: r[0])
            large = max(rows, key=lambda r: (r[1], r[0]))
            changes = []
            with state.db:
                for tid, size in (ordinary, large):
                    eid = state.db.execute(
                        "SELECT entity_id FROM entity WHERE title_id=? ORDER BY entity_id LIMIT 1",
                        (tid,),
                    ).fetchone()[0]
                    state.db.execute(
                        "UPDATE entity SET display_title='Publication benchmark metadata (measured)',observed_at=? WHERE entity_id=?",
                        (now, eid),
                    )
                    changes.append(
                        {"title_id": tid, "entity_id": eid, "partition_episodes": size}
                    )
            result[provider] = {
                "initial_full": first,
                "generated_changes": changes,
                "ledger": metrics(state.db),
            }
        finally:
            state.close()
    return result


async def incremental(config: Config, now: int) -> dict:
    app = create_app(config.output_dir, "publication-test-token", now=now)
    result = {"providers": {}, "queries": [], "targeted": [], "last_good": {}}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1",
        headers={"Authorization": "Bearer publication-test-token"},
    ) as http:
        for provider in PROVIDERS:
            root = provider_root(config.output_dir, provider)
            current = json.loads((root / "current.json").read_text())
            with sqlite3.connect(root / current["database"]) as db:
                expected_total = db.execute(
                    "SELECT count(*) FROM release r JOIN entity e USING(entity_id) WHERE e.kind='episode' AND r.first_seen_at>=?",
                    (now - 30 * 86400,),
                ).fetchone()[0]
            ready = threading.Event()
            job = asyncio.create_task(
                asyncio.to_thread(one, config, provider, now, False, ready)
            )
            while not ready.is_set() and not job.done():
                await asyncio.sleep(0.05)
            attempts = 0
            while not job.done() or attempts < 2:
                start = time.monotonic()
                response = await http.post(
                    "/catalog/v1/query",
                    json=Request(
                        provider=provider,
                        operation="recent",
                        params={"t": "tvsearch"},
                        limit=100,
                    ).model_dump(),
                )
                body = response.json()
                assert body["total"] == expected_total
                assert response.status_code == 200 and all(
                    r["provider"] == provider for r in body["rows"]
                )
                result["queries"].append(
                    {
                        "provider": provider,
                        "status": response.status_code,
                        "publication_inflight": not job.done(),
                        "total": body["total"],
                        "rows": len(body["rows"]),
                        "seconds": round(time.monotonic() - start, 6),
                    }
                )
                attempts += 1
                if attempts >= 30:
                    break  # Bounded overlap probe, never an endurance load test.
                await asyncio.sleep(0.05)
            result["providers"][provider] = await job
            # Compare ordinary/large title retrieval to independent SQL, with
            # exact totals and identity sets at every bounded response page.
            current = json.loads((root / "current.json").read_text())
            seed_result = json.loads(
                (config.output_dir.parent / "seed-result.json").read_text()
            )
            with sqlite3.connect(root / current["database"]) as db:
                for selected in seed_result[provider]["generated_changes"]:
                    tid = selected["title_id"]
                    ids = {
                        r[0]
                        for r in db.execute(
                            "SELECT r.release_id FROM release r JOIN entity e USING(entity_id) WHERE e.title_id=? AND r.first_seen_at>=?",
                            (tid, now - 30 * 86400),
                        )
                    }
                    received = set()
                    offset = 0
                    while True:
                        begin = time.monotonic()
                        response = await http.post(
                            "/catalog/v1/query",
                            json=Request(
                                provider=provider,
                                operation="native",
                                params={"t": "search"},
                                title_ids=[tid],
                                limit=100,
                                offset=offset,
                            ).model_dump(),
                        )
                        body = response.json()
                        assert response.status_code == 200 and body["total"] == len(ids)
                        assert all(r["provider"] == provider for r in body["rows"])
                        received.update(r["release_id"] for r in body["rows"])
                        result["targeted"].append(
                            {
                                "provider": provider,
                                "title_id": tid,
                                "partition_episodes": selected["partition_episodes"],
                                "total": body["total"],
                                "rows": len(body["rows"]),
                                "seconds": round(time.monotonic() - begin, 6),
                            }
                        )
                        offset += len(body["rows"])
                        if offset >= len(ids):
                            break
                        assert body["rows"] and offset <= 20000
                    assert received == ids
            pointer = (root / "current.json").read_bytes()

            def fail(*args, **kwargs):
                raise ValueError("controlled export failure")

            def last_good(provider=provider):
                state = State(config.state_dir / (provider + ".sqlite"), provider)
                try:
                    with patch("catalog_worker.read_catalog.copy", fail):
                        try:
                            publish(config, state, now)
                        except ValueError:
                            pass
                        else:
                            raise AssertionError("expected controlled failure")
                finally:
                    state.close()

            await asyncio.to_thread(last_good)
            assert (root / "current.json").read_bytes() == pointer and not (
                root / "staging.sqlite"
            ).exists()
            result["last_good"][provider] = True
        pointer = config.output_dir / "current.json"
        saved = pointer.read_bytes()
        pointer.unlink()
        try:
            statuses = []
            for provider in PROVIDERS:
                response = await http.post(
                    "/catalog/v1/query",
                    json=Request(
                        provider=provider,
                        operation="recent",
                        params={"t": "search"},
                        limit=100,
                    ).model_dump(),
                )
                statuses.append(response.status_code)
            assert statuses == [503, 200]
            result["provider_isolation"] = statuses
        finally:
            pointer.write_bytes(saved)
    return result


async def legacy_check(config: Config, now: int) -> dict:
    """Run only with the installed v5 image after the copied-state downgrade."""
    app = create_app(config.output_dir, "publication-test-token", now=now)
    result = {}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://127.0.0.1",
        headers={"Authorization": "Bearer publication-test-token"},
    ) as http:
        for provider in PROVIDERS:
            state = State(config.state_dir / (provider + ".sqlite"), provider)
            try:
                assert (
                    state.db.execute("SELECT version FROM worker_schema").fetchone()[0]
                    == 5
                )
            finally:
                state.close()
            root = provider_root(config.output_dir, provider)
            metadata = json.loads((root / "current.json").read_text())
            with sqlite3.connect(
                (root / metadata["database"]).as_uri() + "?mode=ro&immutable=1",
                uri=True,
            ) as db:
                total = db.execute(
                    "SELECT count(*) FROM release r JOIN entity e USING(entity_id) WHERE e.kind='episode' AND r.first_seen_at>=?",
                    (now - 30 * 86400,),
                ).fetchone()[0]
            response = await http.post(
                "/catalog/v1/query",
                json=Request(
                    provider=provider,
                    operation="recent",
                    params={"t": "tvsearch"},
                    limit=100,
                ).model_dump(),
            )
            body = response.json()
            assert (
                response.status_code == 200
                and body["total"] == total
                and all(row["provider"] == provider for row in body["rows"])
            )
            result[provider] = {
                "v5_open": "passed",
                "query_status": 200,
                "exact_total": total,
            }
    return result


def compare(root: Path, config: Config) -> dict:
    result = {}
    for provider in PROVIDERS:
        current = provider_root(config.output_dir, provider)
        old = provider_root(root / "legacy", provider)
        latest = json.loads((current / "current.json").read_text())
        baseline = json.loads((old / "current.json").read_text())
        with sqlite3.connect(
            (current / latest["database"]).as_uri() + "?mode=ro&immutable=1", uri=True
        ) as db:
            db.execute("PRAGMA temp_store=MEMORY")
            db.execute(
                "ATTACH DATABASE ? AS baseline",
                ((old / baseline["database"]).as_uri() + "?mode=ro&immutable=1",),
            )
            differences = {
                t: db.execute(
                    f"SELECT count(*) FROM (SELECT * FROM main.{t} EXCEPT SELECT * FROM baseline.{t})"
                ).fetchone()[0]
                + db.execute(
                    f"SELECT count(*) FROM (SELECT * FROM baseline.{t} EXCEPT SELECT * FROM main.{t})"
                ).fetchone()[0]
                for t in latest["counts"]
            }
            assert not any(differences.values()), "full/incremental publication differs"
            # Re-admit the incremental output with the full untrusted validator.
            schema.validate(current / latest["database"], latest)
            result[provider] = {
                "public_row_differences": differences,
                "full_independent_validation": "passed",
            }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode", choices=("seed", "legacy", "incremental", "legacy-check")
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    args = parser.parse_args()
    if (
        not (args.state / "COPY_ONLY").is_file()
        or not (args.root / "COPY_ONLY").is_file()
    ):
        raise ValueError("explicit disposable copies required")
    now_path = args.root / "clock.json"
    if args.mode == "seed":
        # Earlier private replays advanced retry clocks. Publish after every
        # retained public timestamp rather than weakening timestamp validation.
        now = int(time.time())
        for provider in PROVIDERS:
            with sqlite3.connect(args.state / (provider + ".sqlite")) as db:
                for table, column in (
                    ("title", "observed_at"),
                    ("entity", "observed_at"),
                    ("release", "observed_at"),
                    ("canonical_title", "checked_at"),
                    ("canonical_episode", "checked_at"),
                    ("catalog", "listing_checked_at"),
                ):
                    now = max(
                        now,
                        db.execute(
                            f"SELECT coalesce(max({column}),0) FROM {table}"
                        ).fetchone()[0],
                    )
        now_path.write_text(json.dumps(now))
    now = json.loads(now_path.read_text())
    config = configuration(
        args.root, args.state, "legacy" if args.mode == "legacy" else "modern"
    )
    if args.mode == "seed":
        result = seed(config, now)
    elif args.mode == "legacy":
        result = {p: one(config, p, now, True) for p in PROVIDERS}
    elif args.mode == "legacy-check":
        result = asyncio.run(legacy_check(config, now))
    else:
        result = asyncio.run(incremental(config, now))
        result["comparison"] = compare(args.root, config)
    (args.root / (args.mode + "-result.json")).write_text(
        json.dumps(result, indent=2) + "\n"
    )
    print(json.dumps({"mode": args.mode, "status": "passed"}))


if __name__ == "__main__":
    main()
