"""Finite common-cohort unchanged replay with installed legacy or current code.

Run each phase in its own network-disabled Linux container at 2 CPU/2 GiB.
Legacy imports deliberately avoid new modules: use the pinned old image without
PYTHONPATH; use the candidate wheels/source overlay for the current phase.
"""

import argparse
import json
import resource
import sqlite3
import time
from pathlib import Path

from catalog_worker.canonical_cache import apply
from catalog_worker.state import State


def run(root: Path, phase: str) -> dict:
    if (
        not (root / "candidate/COPY_ONLY").is_file()
        or (root / "candidate").resolve() == (root / "baseline").resolve()
    ):
        raise ValueError("separate explicit disposable copies required")
    legacy = root / "legacy-compare"
    if phase == "legacy":
        legacy.mkdir(mode=0o700, exist_ok=False)
    result = {}
    begin = time.monotonic()
    for provider, stem in [("aniworld.to", "aniworld"), ("s.to", "sto")]:
        baseline = root / "baseline" / (provider + ".sqlite")
        if baseline.with_name(baseline.name + "-wal").exists():
            raise ValueError("WAL-free consistent frozen baseline required")
        with sqlite3.connect(
            baseline.as_uri() + "?mode=ro&immutable=1", uri=True
        ) as source:
            common = {
                r[0] for r in source.execute("SELECT title_id FROM canonical_cache")
            }
            file = (legacy if phase == "legacy" else root / "candidate") / baseline.name
            if phase == "legacy":
                with sqlite3.connect(file) as target:
                    source.backup(target)
        cohort = json.loads((root / (stem + "-cohort.json")).read_text())
        if cohort["provider"] != provider or not 1 <= len(cohort["titles"]) <= 100:
            raise ValueError("bounded provider cohort required")
        state = State(file, provider)
        try:
            db = state.db
            tids = [r["title_id"] for r in cohort["titles"] if r["title_id"] in common]
            passes = []
            for _ in range(2):
                cpu, start, changed = (
                    time.process_time(),
                    time.monotonic(),
                    db.total_changes,
                )
                maps = db.execute("SELECT count(*) FROM canonical_episode").fetchone()[
                    0
                ]
                outcomes = {}
                for tid in tids:
                    checked = db.execute(
                        "SELECT checked_at FROM canonical_cache WHERE title_id=?",
                        (tid,),
                    ).fetchone()[0]
                    with db:
                        outcome = apply(state, tid, checked)
                    outcomes[outcome] = outcomes.get(outcome, 0) + 1
                passes.append(
                    {
                        "titles": len(tids),
                        "duration_s": round(time.monotonic() - start, 4),
                        "cpu_s": round(time.process_time() - cpu, 4),
                        "sqlite_row_mutations": db.total_changes - changed,
                        "new_maps": db.execute(
                            "SELECT count(*) FROM canonical_episode"
                        ).fetchone()[0]
                        - maps,
                        "outcomes": outcomes,
                    }
                )
            result[provider] = passes
        finally:
            state.close()
    measured = {
        "providers": result,
        "duration_s": round(time.monotonic() - begin, 4),
        "rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
    }
    for name in ("memory.peak", "memory.events", "io.stat"):
        measured[name] = Path("/sys/fs/cgroup", name).read_text()
    return measured


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--phase", choices=["legacy", "current"], required=True)
    args = parser.parse_args()
    (args.root / ("unchanged-" + args.phase + ".json")).write_text(
        json.dumps(run(args.root.resolve(), args.phase), indent=2) + "\n"
    )
