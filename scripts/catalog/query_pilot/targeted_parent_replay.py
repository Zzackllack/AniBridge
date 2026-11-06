"""Offline recorded-metadata parent repair through the real enrichment path."""

import argparse
import asyncio
import json
import time
from pathlib import Path

from catalog_core.providers.transport import Fetch
from catalog_worker.canonical import Enricher
from catalog_worker.state import State
from mapping_replay import metrics, resources


async def replay(
    root: Path, search_path: Path, descriptor_path: Path, v1_path: Path
) -> dict:
    evidence = json.loads(descriptor_path.read_text())
    v1 = json.loads(v1_path.read_text())["languages"]["v1en"]["payload"]
    searches = json.loads(search_path.read_text())
    state = State(root / "candidate/aniworld.to.sqlite", "aniworld.to")
    if not (root / "candidate/COPY_ONLY").is_file():
        raise ValueError("disposable copy required")
    tid = next(
        row["title_id"]
        for row in searches
        if any(
            item.get("tvdbId") == evidence["languages"]["eng"]["payload"]["tvdbId"]
            for item in row.get("payload") or []
        )
    )
    source_name = state.db.execute(
        "SELECT display_title FROM title WHERE title_id=?", (tid,)
    ).fetchone()[0]
    search = next(row["payload"] for row in searches if row["title_id"] == tid)
    calls = []

    async def fetch(origin: str, path: str, **kwargs) -> Fetch:
        calls.append(
            "search"
            if "search" in path
            else "translation"
            if "/deu/" in path
            else "descriptor"
        )
        if path == "/v2/tvdb/search":
            payload = search if kwargs["query"]["term"] == source_name else []
        elif path == "/v2/tvdb/shows/eng/" + evidence["id"] + "/official":
            payload = evidence["languages"]["eng"]["payload"]
        elif path.endswith("/" + evidence["id"]):
            payload = v1
        elif "/deu/" in path:
            payload = evidence["languages"]["deu"]["payload"]
        else:
            raise ValueError("unrecorded canonical endpoint")
        return Fetch("ok", body=json.dumps(payload).encode(), requests=1, status=200)

    now = int(time.time())
    before = metrics(state.db)
    start = time.monotonic()
    cpu = resources()
    enricher = Enricher(
        {"tv": "skyhook", "movie": "off", "episode_languages": ["deu"]},
        fetcher=fetch,
        clock=lambda: now,
    )
    try:
        worked = await enricher.tick(state, now, title_id=tid)
        after = metrics(state.db)
        db = state.db
        db.execute(
            "ATTACH DATABASE ? AS b",
            ((root / "baseline/aniworld.to.sqlite").as_uri() + "?mode=ro&immutable=1",),
        )
        preserved = {
            "release_or_first_seen_changed": db.execute(
                "SELECT count(*) FROM b.release old LEFT JOIN main.release new USING(release_id) WHERE new.release_id IS NULL OR old.first_seen_at<>new.first_seen_at"
            ).fetchone()[0],
            "work_changed": db.execute(
                "SELECT count(*) FROM (SELECT * FROM b.work EXCEPT SELECT * FROM main.work)"
            ).fetchone()[0],
            "old_maps_removed_or_repointed": db.execute(
                "SELECT count(*) FROM b.canonical_episode old LEFT JOIN main.canonical_episode new USING(mapping_id,entity_id) WHERE new.mapping_id IS NULL OR new.season<>old.season OR new.episode<>old.episode"
            ).fetchone()[0],
        }
        return {
            "worked": worked,
            "outcome": enricher.last_work,
            "requests": len(calls),
            "request_types": calls,
            "before": before,
            "after": after,
            "preservation": preserved,
            "duration_s": round(time.monotonic() - start, 4),
            "resources_before": cpu,
            "resources_after": resources(),
        }
    finally:
        await enricher.close()
        state.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("root", "searches", "descriptor", "v1", "output"):
        parser.add_argument("--" + key, type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(
            asyncio.run(replay(args.root, args.searches, args.descriptor, args.v1)),
            indent=2,
        )
        + "\n"
    )
