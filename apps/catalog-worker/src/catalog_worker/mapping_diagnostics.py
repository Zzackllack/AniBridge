"""Read-only, bounded correspondence replay. Reports contain counts and IDs only."""

import argparse
import hashlib
import json
import sqlite3
import time
from collections import Counter
from contextlib import closing
from pathlib import Path

from .correspondence import summary
from .state import State

SEED = "mapping-2026-10-14-v1"


def readonly_uri(filename: Path, immutable_copy: bool) -> str:
    if immutable_copy and filename.with_name(filename.name + "-wal").exists():
        raise ValueError("immutable diagnostics require a WAL-free consistent backup")
    return (
        filename.resolve().as_uri()
        + "?mode=ro"
        + ("&immutable=1" if immutable_copy else "")
    )


def select(db: sqlite3.Connection) -> list[dict]:
    """Freeze ten large gaps and twenty ordinary titles across size/outcome strata."""
    rows = db.execute(
        "SELECT e.title_id,count(*) AS episodes,sum(NOT EXISTS(SELECT 1 FROM canonical_episode c WHERE c.entity_id=e.entity_id)) AS gaps "
        "FROM entity e WHERE e.kind='episode' GROUP BY e.title_id"
    ).fetchall()
    largest = sorted((r for r in rows if r[2]), key=lambda r: (-r[2], r[0]))[:10]
    selected = {r[0] for r in largest}
    strata = {}
    for row in rows:
        if row[0] in selected:
            continue
        languages = tuple(
            r[0]
            for r in db.execute(
                "SELECT DISTINCT r.language FROM release r JOIN entity e USING(entity_id) WHERE e.title_id=? ORDER BY r.language",
                (row[0],),
            )
        )
        key = (row[1] > 100, row[2] == 0, languages)
        strata.setdefault(key, []).append(row)
    for values in strata.values():
        values.sort(key=lambda r: hashlib.sha256((SEED + r[0]).encode()).digest())
    ordinary = []
    while len(ordinary) < 20 and any(strata.values()):
        for key in sorted(strata):
            if strata[key] and len(ordinary) < 20:
                ordinary.append(strata[key].pop(0))
    return [
        {
            "title_id": row[0],
            "episodes": row[1],
            "gaps": row[2],
            "cohort": "large" if row in largest else "ordinary",
            "split": "development" if i % 2 == 0 else "held_out",
        }
        for i, row in enumerate(largest + ordinary)
    ]


def inspect(
    filename: Path,
    provider: str,
    tids: list[str],
    now: int,
    *,
    immutable_copy: bool = False,
) -> dict:
    """Use the same decision path as apply; do not open a worker writer."""
    if not 1 <= len(tids) <= 100 or not all(
        isinstance(tid, str)
        and len(tid) == 64
        and all(c in "0123456789abcdef" for c in tid)
        for tid in tids
    ):
        raise ValueError("one to 100 bounded title IDs required")
    uri = readonly_uri(filename, immutable_copy)
    with closing(sqlite3.connect(uri, uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA cache_size=-32768")
        db.execute("BEGIN")
        if db.execute("SELECT provider FROM catalog").fetchone()[0] != provider:
            raise ValueError("wrong diagnostic provider")
        # State methods aren't invoked: only its read connection/provider are needed.
        view = State.__new__(State)
        view.db, view.provider = db, provider
        counts, rows = Counter(), []
        freshness = Counter()
        has_descriptors = bool(
            db.execute(
                "SELECT 1 FROM sqlite_schema WHERE name='canonical_descriptor'"
            ).fetchone()
        )
        max_cache_age = None
        for tid in tids:
            item = summary(view, tid, contextual=True)
            counts.update(item)
            rows.append({"title_id": tid, "rejections": item})
            cache = db.execute(
                "SELECT checked_at FROM canonical_cache WHERE title_id=?", (tid,)
            ).fetchone()
            if cache:
                max_cache_age = max(max_cache_age or 0, max(0, now - cache[0]))
            descriptor = (
                db.execute(
                    "SELECT d.next_due FROM canonical_descriptor d JOIN canonical_title t ON t.external_id=d.external_id WHERE t.title_id=? AND t.namespace='tvdb'",
                    (tid,),
                ).fetchone()
                if has_descriptors
                else None
            )
            freshness[
                "expired"
                if descriptor and descriptor[0] <= now
                else "current"
                if descriptor
                else "unverified_legacy"
                if cache
                else "absent"
            ] += 1
        schedule = db.execute(
            "SELECT count(*),min(next_due),sum(checked_at IS NULL),sum(outcome='source_failure') FROM mapping_input WHERE next_due<=?",
            (now,),
        ).fetchone()
        return {
            "provider": provider,
            "titles_examined": len(tids),
            "counts": dict(counts),
            "eligible_titles": schedule[0],
            "oldest_eligibility_age_s": max(0, now - schedule[1])
            if schedule[1]
            else None,
            "waiting_first_attempt": schedule[2],
            "source_failures": schedule[3],
            "descriptor_freshness": dict(freshness),
            "max_cache_acquisition_age_s": max_cache_age,
            "titles": rows,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--provider", choices=("aniworld.to", "s.to"), required=True)
    parser.add_argument("--cohort", type=Path, required=True)
    parser.add_argument("--freeze", action="store_true")
    parser.add_argument(
        "--immutable-copy",
        action="store_true",
        help="Only for a WAL-free consistent SQLite backup, never live state",
    )
    parser.add_argument("--now", type=int, default=int(time.time()))
    args = parser.parse_args()
    if args.freeze:
        with closing(
            sqlite3.connect(readonly_uri(args.state, args.immutable_copy), uri=True)
        ) as db:
            rows = select(db)
        with args.cohort.open("x") as stream:
            json.dump(
                {"seed": SEED, "provider": args.provider, "titles": rows},
                stream,
                indent=2,
            )
    cohort = json.loads(args.cohort.read_text())
    if cohort["provider"] != args.provider or not 1 <= len(cohort["titles"]) <= 100:
        raise ValueError("invalid diagnostic cohort")
    print(
        json.dumps(
            inspect(
                args.state,
                args.provider,
                [r["title_id"] for r in cohort["titles"]],
                args.now,
                immutable_copy=args.immutable_copy,
            ),
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
