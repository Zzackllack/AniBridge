"""Durable bounded hints and fair targeted/reconciliation admission.

A capped page has no sequence number. Overlap never establishes completeness;
loss of overlap, an outage, unknown labels and parser failures latch a gap.
"""

import json
from typing import TYPE_CHECKING

from catalog_core import identity
from catalog_core.json_codec import require
from catalog_core.providers.recent import Window, signal_path

from .aniworld import Link

if TYPE_CHECKING:
    from .state import State
from .transactions import atomic

MAX_PENDING = 4096


class Signals:
    def __init__(self, state: "State") -> None:
        self.state, self.db = state, state.db

    def status(self) -> dict:
        result = dict(self.db.execute("SELECT * FROM signal_meta").fetchone())
        count, oldest = self.db.execute(
            "SELECT count(*),min(first_observed) FROM signal_pending"
        ).fetchone()
        result.update(pending=count, oldest_pending=oldest)
        if signal_path(self.state.provider) is None:
            result["coverage"] = "unsupported"
        return result

    def reserve(self, now: int, origin: str, lease_s: int) -> bool:
        if signal_path(self.state.provider) is None:
            return False
        with atomic(self.db):
            self.db.execute(
                "UPDATE signal_meta SET origin=?,next_due=0,checked_at=0,coverage='unknown',"
                "gap_since=CASE WHEN origin<>'' THEN coalesce(gap_since,?) ELSE gap_since END WHERE origin<>?",
                (origin, now, origin),
            )
            return (
                self.db.execute(
                    "UPDATE signal_meta SET lease_until=? WHERE next_due<=? AND lease_until<=?",
                    (now + lease_s, now, now),
                ).rowcount
                == 1
            )

    def failed(self, now: int, delay: int) -> None:
        with atomic(self.db):
            self.db.execute(
                "UPDATE signal_meta SET lease_until=0,next_due=?,coverage='gap',gap_since=coalesce(gap_since,?)",
                (now + delay, now),
            )

    def enqueue(self, path: str, tid: str, kind: str, now: int, language=None) -> None:
        require(
            self.db.execute(
                "SELECT 1 FROM signal_pending WHERE path=?", (path,)
            ).fetchone()
            or self.db.execute("SELECT count(*) FROM signal_pending").fetchone()[0]
            < MAX_PENDING,
            "signal pending overflow",
        )
        self.db.execute(
            "INSERT INTO work(path,title_id,kind,due) VALUES(?,?,?,?) ON CONFLICT(path) DO UPDATE SET due=min(work.due,excluded.due)",
            (path, tid, kind, now),
        )
        old = self.db.execute(
            "SELECT expected FROM signal_pending WHERE path=?", (path,)
        ).fetchone()
        expected = set(json.loads(old[0])) if old else set()
        if language:
            expected.add(language)
        self.db.execute(
            "INSERT INTO signal_pending(path,due,first_observed,expected) VALUES(?,?,?,?) "
            "ON CONFLICT(path) DO UPDATE SET expected=excluded.expected,generation=generation+1,due=min(signal_pending.due,excluded.due)",
            (path, now, now, json.dumps(sorted(expected))),
        )

    def accept(self, window: Window, now: int, interval: int) -> None:
        state = self.state
        old = self.status()
        previous = {
            tuple(row)
            for row in self.db.execute("SELECT path,language FROM signal_window")
        }
        current = {(r.path, r.language or "") for r in window.entries}
        overlap = len(previous & current)
        gap = (
            not current
            or bool(previous)
            and not overlap
            or old["checked_at"] > 0
            and now - old["checked_at"] > interval * 2
            or window.unknown_languages > 0
            or window.pagination
        )
        with atomic(self.db):
            for entry in window.entries:
                key = (entry.path, entry.language or "")
                if key in previous:
                    continue
                eid = identity.entity_id(state.provider, entry.path)
                if (
                    entry.language
                    and self.db.execute(
                        "SELECT 1 FROM release WHERE release_id=?",
                        (identity.release_id(state.provider, eid, entry.language),),
                    ).fetchone()
                ):
                    continue
                title_path = entry.path.split("/staffel-")[0].split("/filme/")[0]
                tid = identity.title_id(state.provider, title_path)
                if not self.db.execute(
                    "SELECT 1 FROM title WHERE title_id=?", (tid,)
                ).fetchone():
                    state.discover(Link(title_path, entry.title), now)
                # Only missing parent metadata is needed for an established title.
                for path, kind in (
                    (title_path, "title"),
                    (entry.path.rsplit("/", 1)[0], "season"),
                ):
                    work = self.db.execute(
                        "SELECT checked_at FROM work WHERE path=?", (path,)
                    ).fetchone()
                    if work is None or work[0] is None:
                        self.enqueue(path, tid, kind, now)
                self.enqueue(entry.path, tid, "episode", now, entry.language)
            # Replace the small observed window atomically with its checkpoints.
            # No absence/deletion logic runs on this incomplete enumeration.
            self.db.execute("DELETE FROM signal_window")
            self.db.executemany(
                "INSERT INTO signal_window VALUES(?,?)", sorted(current)
            )
            self.db.execute(
                "UPDATE signal_meta SET checked_at=?,next_due=?,lease_until=0,entries=?,overlaps=?,"
                "unknown_languages=?,polls=polls+1,coverage=?,gap_since=CASE WHEN ? THEN coalesce(gap_since,?) ELSE gap_since END",
                (
                    now,
                    now + interval,
                    len(current),
                    overlap,
                    window.unknown_languages,
                    "gap"
                    if gap or old["gap_since"] is not None
                    else "window-overlap"
                    if old["checked_at"]
                    else "unknown",
                    gap,
                    now,
                ),
            )

    def claim(
        self, now: int, slot: int, lease_s: int, reconciliation_s: int, hourly: int
    ) -> dict | None:
        def targeted():
            return self.db.execute(
                "SELECT w.*,p.generation AS signal_generation FROM signal_pending p JOIN work w USING(path) "
                "WHERE p.due<=? AND w.due<=? AND w.lease_until<=? "
                "ORDER BY CASE w.kind WHEN 'title' THEN 0 WHEN 'season' THEN 1 ELSE 2 END,p.first_observed,w.path LIMIT 1",
                (now, now, now),
            ).fetchone()

        def new():
            # Upgrade backlog: one fresh season observation can replace many
            # never-checked episode pages. Checkpoint even unsupported rows so
            # the fallback does not repeatedly fetch the same season.
            batch = self.db.execute(
                "SELECT w.* FROM work w WHERE kind='season' AND checked_at IS NOT NULL AND failures=0 AND lease_until<=? "
                "AND NOT EXISTS(SELECT 1 FROM season_batch_checkpoint b WHERE b.path=w.path) "
                "AND EXISTS(SELECT 1 FROM work e WHERE e.title_id=w.title_id AND e.kind='episode' AND e.checked_at IS NULL AND e.path LIKE w.path||'/%') "
                "ORDER BY w.due,w.path LIMIT 1",
                (now,),
            ).fetchone()
            if batch is not None:
                return batch
            return self.db.execute(
                "SELECT * FROM work w WHERE checked_at IS NULL AND due<=? AND lease_until<=? "
                "AND NOT EXISTS(SELECT 1 FROM omissions o WHERE o.kind='title' AND o.id=w.title_id AND o.tombstoned=1) "
                "AND NOT EXISTS(SELECT 1 FROM signal_pending p WHERE p.path=w.path) ORDER BY due,path LIMIT 1",
                (now, now),
            ).fetchone()

        def history():
            self.db.execute(
                "DELETE FROM reconciliation_start WHERE at<=?", (now - 3600,)
            )
            if self.db.execute("SELECT count(*) FROM reconciliation_start").fetchone()[
                0
            ] >= max(1, hourly // 5):
                return None
            return self.db.execute(
                "SELECT * FROM work w WHERE checked_at IS NOT NULL AND (checked_at<=? OR failures>0) AND due<=? AND lease_until<=? "
                "AND NOT EXISTS(SELECT 1 FROM signal_pending p WHERE p.path=w.path) "
                "AND NOT EXISTS(SELECT 1 FROM omissions o WHERE o.kind='title' AND o.id=w.title_id AND o.tombstoned=1) "
                "ORDER BY checked_at,path LIMIT 1",
                (now - reconciliation_s, now, now),
            ).fetchone()

        choices = (
            (history, new, targeted)
            if slot % 5 == 4
            else (new, targeted, history)
            if slot % 5 in (2, 3)
            else (targeted, new, history)
        )
        row = next((row for choose in choices if (row := choose()) is not None), None)
        if row is None:
            return None
        self.db.execute(
            "UPDATE work SET lease_until=? WHERE path=?", (now + lease_s, row["path"])
        )
        result = dict(row)
        result["incremental"] = True
        result["targeted"] = "signal_generation" in result
        result["batch_bootstrap"] = (
            result["kind"] == "season"
            and result["checked_at"] is not None
            and self.db.execute(
                "SELECT 1 FROM season_batch_checkpoint WHERE path=?", (result["path"],)
            ).fetchone()
            is None
        )
        return result

    def settle(self, work: dict, now: int, *, success: bool) -> None:
        generation = work.get("signal_generation")
        if generation is None:
            return
        with atomic(self.db):
            row = self.db.execute(
                "SELECT * FROM signal_pending WHERE path=? AND generation=?",
                (work["path"], generation),
            ).fetchone()
            if row is None:
                # A concurrent newly observed variant must survive this old checkpoint.
                self.db.execute(
                    "UPDATE work SET due=min(due,(SELECT due FROM signal_pending WHERE path=?)) WHERE path=? AND EXISTS(SELECT 1 FROM signal_pending WHERE path=?)",
                    (work["path"], work["path"], work["path"]),
                )
                return
            eid = identity.entity_id(self.state.provider, work["path"])
            expected = json.loads(row["expected"])
            observed = {
                r[0]
                for r in self.db.execute(
                    "SELECT language FROM release WHERE entity_id=?", (eid,)
                )
            }
            checked = self.db.execute(
                "SELECT checked_at FROM work WHERE path=?", (work["path"],)
            ).fetchone()[0]
            if success and checked == now and set(expected) <= observed:
                self.db.execute(
                    "DELETE FROM signal_pending WHERE path=? AND generation=?",
                    (work["path"], generation),
                )
            else:
                due = self.db.execute(
                    "SELECT due FROM work WHERE path=?", (work["path"],)
                ).fetchone()[0]
                retry_due = max(now + (60 if success else 1), due if not success else 0)
                self.db.execute(
                    "UPDATE work SET due=? WHERE path=?", (retry_due, work["path"])
                )
                self.db.execute(
                    "UPDATE signal_pending SET due=?,failures=failures+1 WHERE path=? AND generation=?",
                    (
                        retry_due,
                        work["path"],
                        generation,
                    ),
                )
                self.db.execute(
                    "UPDATE signal_meta SET coverage='gap',gap_since=coalesce(gap_since,?)",
                    (now,),
                )
