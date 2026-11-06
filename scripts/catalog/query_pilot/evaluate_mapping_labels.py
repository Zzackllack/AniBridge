"""Read-only comparison against reviewed IDs/names, never native number ground truth."""

import argparse
import json
import sqlite3
from collections import Counter
from contextlib import closing
from pathlib import Path


def evaluate(root: Path, labels: dict) -> dict:
    result = {}
    for provider in ("aniworld.to", "s.to"):
        rows = [r for r in labels["cases"] if r["provider"] == provider]
        counts = {
            split: {phase: Counter() for phase in ("before", "after")}
            for split in ("development", "held_out")
        }
        uncertain = []
        ambiguity = {}
        for phase, folder in [("before", "baseline"), ("after", "candidate")]:
            with closing(
                sqlite3.connect(
                    (root / folder / (provider + ".sqlite")).as_uri()
                    + "?mode=ro&immutable=1",
                    uri=True,
                )
            ) as db:
                for case in rows:
                    found = db.execute(
                        "SELECT c.season,c.episode,c.external_episode_id FROM canonical_episode c JOIN canonical_title t USING(mapping_id) WHERE c.entity_id=? AND t.namespace='tvdb'",
                        (case["entity_id"],),
                    ).fetchall()
                    out = counts[case["split"]][phase]
                    out["cases"] += 1
                    if case["label"] == "positive":
                        out["labelled_positive"] += 1
                        expected = case["expected"]
                        valid = [
                            r
                            for r in found
                            if r[0] == expected["season"]
                            and r[1] == expected["episode"]
                            and (r[2] is None or r[2] == expected["tvdb_episode_id"])
                        ]
                        out["correct"] += bool(valid)
                        out["wrong"] += bool(found and not valid)
                        out["unresolved_positive"] += not found
                    else:
                        out["nonpositive"] += 1
                        out["nonpositive_mapped"] += bool(found)
                        if found:
                            uncertain.append(
                                {
                                    "case": case["case"],
                                    "phase": phase,
                                    "label": case["label"],
                                    "split": case["split"],
                                }
                            )
                supplemental = [
                    entity
                    for group in labels.get("supplementary_ambiguity", {}).get(
                        provider, []
                    )
                    for entity in group["entities"]
                ]
                ambiguity[phase] = {
                    "cases": len(supplemental),
                    "mapped": sum(
                        bool(
                            db.execute(
                                "SELECT 1 FROM canonical_episode WHERE entity_id=? LIMIT 1",
                                (entity["entity_id"],),
                            ).fetchone()
                        )
                        for entity in supplemental
                    ),
                }
        result[provider] = {
            "splits": counts,
            "mapped_outside_positive_labels": uncertain,
            "supplementary_ambiguity": ambiguity,
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_text(
        json.dumps(evaluate(args.root, json.loads(args.labels.read_text())), indent=2)
        + "\n"
    )
