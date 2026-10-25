"""Finite offline full-ledger/cohort replay on explicitly disposable SQLite copies.

Mount baseline read-only and run with --network none, --cpus 2, --memory 2g.
No provider fetches, reset, deletion, inferred numbering or live-state writer.
Private input fixtures may contain names; output is allowlisted aggregate counts.
"""

import argparse
import json
import resource
import sqlite3
import time
from collections import Counter
from pathlib import Path

from catalog_worker import canonical_cache, descriptors, parent_evidence
from catalog_worker.correspondence import summary
from catalog_worker.state import State


def metrics(db: sqlite3.Connection) -> dict:
    return {
        "episodes": db.execute(
            "SELECT count(*) FROM entity WHERE kind='episode'"
        ).fetchone()[0],
        "usable_episodes": db.execute(
            "SELECT count(*) FROM entity e WHERE kind='episode' AND EXISTS(SELECT 1 FROM release r WHERE r.entity_id=e.entity_id)"
        ).fetchone()[0],
        "usable_mapped": db.execute(
            "SELECT count(*) FROM entity e WHERE kind='episode' AND EXISTS(SELECT 1 FROM release r WHERE r.entity_id=e.entity_id) AND EXISTS(SELECT 1 FROM canonical_episode c WHERE c.entity_id=e.entity_id)"
        ).fetchone()[0],
        "maps": db.execute("SELECT count(*) FROM canonical_episode").fetchone()[0],
        "releases": db.execute("SELECT count(*) FROM release").fetchone()[0],
    }


def resources() -> dict:
    result = {
        "cpu_s": round(time.process_time(), 4),
        "rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    for name in ("cpu.stat", "memory.stat", "memory.events", "io.stat", "memory.peak"):
        path = Path("/sys/fs/cgroup") / name
        if path.exists():
            result[name] = path.read_text()
    return result


def verified_parent(state: State, tid: str, payload: dict) -> bool:
    return (
        parent_evidence.check(
            state, tid, str(payload["tvdbId"]), parent_evidence.compact(payload)
        )
        == "verified"
    )


def run(args) -> dict:
    if (
        args.baseline.resolve() == args.candidate.resolve()
        or not (args.candidate / "COPY_ONLY").is_file()
    ):
        raise ValueError("explicit disposable copy required")
    started = time.monotonic()
    result = {
        "profile": "2 CPU / 2 GiB, network disabled",
        "resources_before": resources(),
        "providers": {},
    }
    canonical = (
        {r["id"]: r for r in json.loads(args.canonical.read_text())}
        if args.canonical
        else {}
    )
    for provider, stem in [("aniworld.to", "aniworld"), ("s.to", "sto")]:
        begin = time.monotonic()
        state = State(args.candidate / (provider + ".sqlite"), provider)
        db = state.db
        db.execute(
            "ATTACH DATABASE ? AS baseline",
            (
                (args.baseline / (provider + ".sqlite")).resolve().as_uri()
                + "?mode=ro&immutable=1",
            ),
        )
        with sqlite3.connect(
            (args.baseline / (provider + ".sqlite")).resolve().as_uri()
            + "?mode=ro&immutable=1",
            uri=True,
        ) as baseline:
            before = metrics(baseline)
        item = {
            "before": before,
            "rejections_before": Counter(),
            "rejections_after": Counter(),
            "descriptor_parent_blocked": 0,
        }
        tids = [
            r[0]
            for r in db.execute(
                "SELECT title_id FROM canonical_cache ORDER BY title_id"
            )
        ]
        apply_counts = Counter()
        for tid in tids:
            with db:
                cached = db.execute(
                    "SELECT checked_at FROM canonical_cache WHERE title_id=?", (tid,)
                ).fetchone()[0]
                apply_counts[
                    canonical_cache.apply(state, tid, cached, examined_at=args.now)
                ] += 1
        item["cached_inputs_only"] = metrics(db)
        item["first_pass"] = dict(apply_counts)
        cohort = json.loads((args.cohorts / (stem + "-cohort.json")).read_text())[
            "titles"
        ]
        phases = []
        for row in cohort:
            tid = row["title_id"]
            parent = db.execute(
                "SELECT external_id FROM canonical_title WHERE title_id=? AND namespace='tvdb'",
                (tid,),
            ).fetchone()
            if not parent or parent[0] not in canonical:
                continue
            evidence = canonical[parent[0]]["languages"]
            primary = evidence.get("eng", {}).get("payload")
            translated = evidence.get("deu", {}).get("payload")
            if not primary or not verified_parent(state, tid, primary):
                item["descriptor_parent_blocked"] += 1
                continue
            cache = db.execute(
                "SELECT input_hash,matcher FROM canonical_cache WHERE title_id=?",
                (tid,),
            ).fetchone()
            if not cache:
                continue
            count0 = db.execute("SELECT count(*) FROM canonical_episode").fetchone()[0]
            records = descriptors.episodes(primary)
            with db:
                descriptors.save(
                    state, parent[0], primary, records, args.now, canonical_cache.TTL
                )
                canonical_cache.store(state, tid, *cache, args.now, records)
                canonical_cache.apply(state, tid, args.now)
            count1 = db.execute("SELECT count(*) FROM canonical_episode").fetchone()[0]
            if (
                translated
                and translated.get("metadataSource") == "tvdb"
                and translated.get("tvdbId") == primary["tvdbId"]
            ):
                records = descriptors.merge(records, descriptors.episodes(translated))
                primary["_episode_languages"] = ["deu"]
                with db:
                    descriptors.save(
                        state,
                        parent[0],
                        primary,
                        records,
                        args.now,
                        canonical_cache.TTL,
                    )
                    canonical_cache.store(state, tid, *cache, args.now, records)
                    canonical_cache.apply(state, tid, args.now)
            count2 = db.execute("SELECT count(*) FROM canonical_episode").fetchone()[0]
            phases.append(
                {
                    "title_id": tid,
                    "split": row["split"],
                    "fresh_primary_maps": count1 - count0,
                    "translated_maps": count2 - count1,
                }
            )
        item["cohort_phases"] = phases
        unchanged = Counter()
        replay_start = time.monotonic()
        for tid in tids:
            with db:
                cached = db.execute(
                    "SELECT checked_at FROM canonical_cache WHERE title_id=?", (tid,)
                ).fetchone()[0]
                unchanged[
                    canonical_cache.apply(state, tid, cached, examined_at=args.now + 1)
                ] += 1
        item["second_pass"] = dict(unchanged)
        item["unchanged_replay_s"] = round(time.monotonic() - replay_start, 4)
        item["after"] = metrics(db)
        item["preservation"] = {
            "release_identity_or_first_seen_changed": db.execute(
                "SELECT count(*) FROM baseline.release b LEFT JOIN main.release r USING(release_id) WHERE r.release_id IS NULL OR r.first_seen_at<>b.first_seen_at"
            ).fetchone()[0],
            "old_maps_removed_or_repointed": db.execute(
                "SELECT count(*) FROM baseline.canonical_episode b LEFT JOIN main.canonical_episode c USING(mapping_id,entity_id) WHERE c.mapping_id IS NULL OR c.season<>b.season OR c.episode<>b.episode"
            ).fetchone()[0],
            "work_retry_or_lease_changed": db.execute(
                "SELECT count(*) FROM baseline.work b JOIN main.work w USING(path) WHERE b.failures<>w.failures OR b.due<>w.due OR b.lease_until<>w.lease_until"
            ).fetchone()[0],
        }
        for table in (
            "quarantine",
            "signal_pending",
            "season_batch_checkpoint",
            "title_schedule",
            "omissions",
        ):
            item["preservation"][table + "_difference"] = db.execute(
                f"SELECT count(*) FROM (SELECT * FROM baseline.{table} EXCEPT SELECT * FROM main.{table})"
            ).fetchone()[0]
        for row in cohort:
            item["rejections_after"].update(
                summary(state, row["title_id"], contextual=True)
            )
        item["rejections_after"] = dict(item["rejections_after"])
        item.pop("rejections_before")
        item["duration_s"] = round(time.monotonic() - begin, 4)
        result["providers"][provider] = item
        state.close()
    result.update(
        duration_s=round(time.monotonic() - started, 4), resources_after=resources()
    )
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("baseline", "candidate", "cohorts", "output"):
        parser.add_argument("--" + option, type=Path, required=True)
    parser.add_argument("--canonical", type=Path)
    parser.add_argument("--now", type=int, default=int(time.time()))
    args = parser.parse_args()
    args.output.write_text(json.dumps(run(args), indent=2) + "\n")
