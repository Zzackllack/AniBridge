"""Replay bounded recorded canonical responses on consistent disposable copies.

Run with network disabled and 2 CPU/2 GiB. Private recordings contain metadata;
the result contains only counts, hashed title IDs and allowlisted failure codes.
The clock advances to existing retry deadlines; no failure or deadline is reset.
"""

import argparse
import asyncio
import json
import sqlite3
import time
from pathlib import Path

from catalog_core.providers.transport import Fetch
from catalog_worker.canonical import Enricher
from catalog_worker.state import State
from mapping_replay import metrics, resources


async def replay(args: argparse.Namespace) -> dict:
    """Use the real lookup path with an offline, exact-route recording fetcher."""
    if args.baseline.resolve() == args.candidate.resolve():
        raise ValueError("separate disposable copies required")
    for root in (args.baseline, args.candidate):
        if not (root / "COPY_ONLY").is_file():
            raise ValueError("disposable copy marker required")
    files = sorted(args.metadata.glob("*.json"))
    records, payloads = [], {}
    for file in files:
        record = json.loads(file.read_text())
        if not isinstance(record, dict) or "source" not in record:
            continue
        record["split"] = (
            "held_out" if file.name.startswith("heldout-") else "development"
        )
        record["provider"] = record["source"].get("provider") or file.name.split("-")[0]
        records.append(record)
        for language, payload in record["payloads"].items():
            key = (record["source"]["external_id"], language)
            # Same identity may appear under both providers; do not overwrite a
            # recording with a later response or silently combine different data.
            if key in payloads and payloads[key] != payload:
                raise ValueError("conflicting recordings")
            payloads[key] = payload
    if not 1 <= len(records) <= 20:
        raise ValueError("one to twenty fixed cases required")
    result = {"network_requests": 0, "resources_before": resources(), "providers": {}}
    started = time.monotonic()
    sources = {"tv": "skyhook", "movie": "off", "episode_languages": ["deu"]}
    for provider in ("aniworld.to", "s.to"):
        filename = args.baseline / (provider + ".sqlite")
        if filename.with_name(filename.name + "-wal").exists():
            raise ValueError("baseline must be a closed consistent backup")
        state = State(args.candidate / (provider + ".sqlite"), provider)
        try:
            # Full-ledger EXCEPT checks can spill to SQL scratch. Keep the finite
            # comparison in the measured cgroup, including with a read-only root.
            state.db.execute("PRAGMA temp_store=MEMORY")
            state.db.execute(
                "ATTACH DATABASE ? AS baseline",
                (filename.resolve().as_uri() + "?mode=ro&immutable=1",),
            )
            with sqlite3.connect(
                filename.resolve().as_uri() + "?mode=ro&immutable=1", uri=True
            ) as db:
                before = metrics(db)
            cases = []
            for record in records:
                if record["provider"] != provider:
                    continue
                tid, external = (
                    record["source"]["title_id"],
                    record["source"]["external_id"],
                )
                if any((external, lang) not in payloads for lang in ("eng", "deu")):
                    cases.append(
                        {
                            "title_id": tid,
                            "split": record["split"],
                            "result": "recording_incomplete",
                        }
                    )
                    continue
                row = state.db.execute(
                    "SELECT * FROM mapping_input WHERE title_id=?", (tid,)
                ).fetchone()
                now = max(int(time.time()), row["next_due"])
                requests = []

                async def fetch(
                    origin: str,
                    path: str,
                    *,
                    external=external,
                    requests=requests,
                    **kwargs,
                ) -> Fetch:
                    for language in ("eng", "deu"):
                        if path == f"/v2/tvdb/shows/{language}/{external}/official":
                            requests.append(language)
                            return Fetch(
                                "ok",
                                json.dumps(payloads[(external, language)]).encode(),
                                status=200,
                                requests=1,
                            )
                    # Search was not recorded; absence is never a successful empty result.
                    raise OSError("unrecorded request")

                count_sql = "SELECT count(*) FROM canonical_episode c JOIN entity e USING(entity_id) WHERE e.title_id=?"
                old_count = state.db.execute(count_sql, (tid,)).fetchone()[0]
                enricher = Enricher(sources, fetcher=fetch, clock=lambda now=now: now)
                try:
                    worked = await enricher.tick(state, now, title_id=tid)
                    new_count = state.db.execute(count_sql, (tid,)).fetchone()[0]
                    failure = enricher.last_failure
                    cases.append(
                        {
                            "title_id": tid,
                            "split": record["split"],
                            "worked": worked,
                            "before_maps": old_count,
                            "after_maps": new_count,
                            "recorded_requests": len(requests),
                            "result": enricher.last_work,
                            "failure_phase": failure.phase if failure else None,
                            "failure_reason": failure.reason if failure else None,
                        }
                    )
                finally:
                    await enricher.close()
            db = state.db
            preservation = {
                "release_identity_or_first_seen_changed": db.execute(
                    "SELECT count(*) FROM baseline.release b LEFT JOIN main.release r USING(release_id) WHERE r.release_id IS NULL OR r.first_seen_at<>b.first_seen_at"
                ).fetchone()[0],
                "old_map_rows_changed": db.execute(
                    "SELECT count(*) FROM (SELECT * FROM baseline.canonical_episode EXCEPT SELECT * FROM main.canonical_episode)"
                ).fetchone()[0],
                "old_parent_identity_changed": db.execute(
                    "SELECT count(*) FROM baseline.canonical_title b LEFT JOIN main.canonical_title c USING(mapping_id) WHERE c.mapping_id IS NULL OR c.title_id<>b.title_id OR c.namespace<>b.namespace OR c.external_id<>b.external_id"
                ).fetchone()[0],
                "work_retry_or_lease_changed": db.execute(
                    "SELECT count(*) FROM (SELECT * FROM baseline.work EXCEPT SELECT * FROM main.work)"
                ).fetchone()[0],
            }
            for table in (
                "quarantine",
                "omissions",
                "season_batch_checkpoint",
                "signal_meta",
                "signal_pending",
                "title_schedule",
                "observation_gap",
                "season_correspondence",
            ):
                preservation[table + "_rows_changed"] = db.execute(
                    f"SELECT count(*) FROM (SELECT * FROM baseline.{table} EXCEPT SELECT * FROM main.{table})"
                ).fetchone()[0]
            assert not any(preservation.values()), "copied ledger preservation failure"
            result["providers"][provider] = {
                "before": before,
                "after": metrics(db),
                "cases": cases,
                "preservation": preservation,
            }
        finally:
            state.close()
    result["wall_s"] = round(time.monotonic() - started, 4)
    result["resources_after"] = resources()
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline", "candidate", "metadata", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(json.dumps(asyncio.run(replay(args)), indent=2) + "\n")
