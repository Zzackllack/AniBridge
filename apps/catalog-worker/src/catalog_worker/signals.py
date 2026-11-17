"""Durable bounded hints and fair targeted/reconciliation admission.

A capped page has no sequence number. Overlap never establishes completeness;
loss of overlap, an outage, unknown labels and parser failures latch a gap.
"""

import hashlib
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
# Overflow stays fail-closed: an observation that cannot be retained must roll
# back rather than silently drop an obligation. Terminal handling below keeps
# never-observable expectations from reaching this bound.
# A feed can advertise a language that never appears on the detail page. After
# this many successful-but-incomplete checks the obligation is quarantined with
# its evidence instead of filling the durable hint budget forever.
MAX_EXPECTED_MISSES = 6
TERMINAL_RETRY_S = 86400
QUARANTINE_KIND = "signal"


def quarantine_digest(path: str) -> str:
    """Stable anomaly identity for one never-observable feed obligation."""
    return hashlib.sha256(("signal:" + path).encode()).hexdigest()


class Signals:
    def __init__(self, state: State) -> None:
        self.state, self.db = state, state.db

    def status(self) -> dict:
        result = dict(self.db.execute("SELECT * FROM signal_meta").fetchone())
        # Terminal obligations keep their labels/generation as evidence but no
        # longer consume the active hint budget or targeted claims.
        count, oldest = self.db.execute(
            "SELECT count(*),min(first_observed) FROM signal_pending WHERE failures<?",
            (MAX_EXPECTED_MISSES,),
        ).fetchone()
        terminal, oldest_terminal = self.db.execute(
            "SELECT count(*),min(first_observed) FROM signal_pending WHERE failures>=?",
            (MAX_EXPECTED_MISSES,),
        ).fetchone()
        result.update(
            pending=count,
            oldest_pending=oldest,
            terminal_pending=terminal,
            oldest_terminal=oldest_terminal,
        )
        quarantined, oldest_quarantined = self.db.execute(
            "SELECT count(*),min(created_at) FROM quarantine WHERE kind=?",
            (QUARANTINE_KIND,),
        ).fetchone()
        result.update(quarantined=quarantined, oldest_quarantined=oldest_quarantined)
        result["gap_parents_pending"] = self.db.execute(
            "SELECT count(*) FROM work WHERE kind IN ('title','season') AND ? IS NOT NULL AND (checked_at IS NULL OR checked_at<=?)",
            (result["gap_since"], result["gap_since"]),
        ).fetchone()[0]
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
        existing = self.db.execute(
            "SELECT expected,failures FROM signal_pending WHERE path=?", (path,)
        ).fetchone()
        expected = set(json.loads(existing["expected"])) if existing else set()
        terminal = existing is not None and existing["failures"] >= MAX_EXPECTED_MISSES
        novel = language is not None and language not in expected
        # A repeated advertisement of an expectation we already track is not new
        # evidence: the `.accept` window can drop and re-advertise the same
        # (path, language). Never reset terminal state, bump the generation or
        # pull polling earlier on that repeat.
        if existing is not None and not novel:
            return
        if language:
            expected.add(language)
        require(
            (existing is not None and not terminal)
            or self.db.execute(
                "SELECT count(*) FROM signal_pending WHERE failures<?",
                (MAX_EXPECTED_MISSES,),
            ).fetchone()[0]
            < MAX_PENDING,
            "signal pending overflow",
        )
        # Fresh advertisement after a quarantine is positive new evidence: drop
        # the anomaly and reopen one bounded attempt window. A repeated advert
        # for an already-expected language returns above and keeps the anomaly.
        self.db.execute(
            "DELETE FROM quarantine WHERE kind=? AND digest=?",
            (QUARANTINE_KIND, quarantine_digest(path)),
        )
        self.db.execute(
            "INSERT INTO work(path,title_id,kind,due) VALUES(?,?,?,?) ON CONFLICT(path) DO UPDATE SET due=min(work.due,excluded.due)",
            (path, tid, kind, now),
        )
        if terminal:
            # Reopen the bounded window; keep first_observed and add the new
            # language. failures resets only because the evidence is genuinely new.
            self.db.execute(
                "UPDATE signal_pending SET failures=0 WHERE path=?", (path,)
            )
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
        self,
        now: int,
        slot: int,
        lease_s: int,
        reconciliation_s: int,
        hourly: int,
        active_s: int = 14400,
    ) -> dict | None:
        def targeted():
            return self.db.execute(
                "SELECT w.*,p.generation AS signal_generation FROM signal_pending p JOIN work w USING(path) "
                "WHERE p.due<=? AND p.failures<? AND w.due<=? AND w.lease_until<=? "
                "ORDER BY CASE w.kind WHEN 'title' THEN 0 WHEN 'season' THEN 1 ELSE 2 END,p.first_observed,w.path LIMIT 1",
                (now, MAX_EXPECTED_MISSES, now, now),
            ).fetchone()

        def new():
            # Upgrade backlog: one fresh season observation can replace many
            # never-checked episode pages. Checkpoint even unsupported rows so
            # the fallback does not repeatedly fetch the same season.
            batch = None
            # A completed migration backlog otherwise scans the whole ledger
            # before every episode claim (1.71s across 16 pilot-size probes).
            # Cache only the empty local probe for a minute, not provider data.
            if now >= self.state.batch_probe_after:
                batch = self.db.execute(
                    "SELECT w.* FROM work w WHERE kind='season' AND checked_at IS NOT NULL AND failures=0 AND lease_until<=? "
                    "AND NOT EXISTS(SELECT 1 FROM season_batch_checkpoint b WHERE b.path=w.path) "
                    "AND EXISTS(SELECT 1 FROM work e WHERE e.title_id=w.title_id AND e.kind='episode' AND e.checked_at IS NULL AND e.path LIKE w.path||'/%') "
                    "ORDER BY w.due,w.path LIMIT 1",
                    (now,),
                ).fetchone()
                if batch is None:
                    self.state.batch_probe_after = now + 60
            if batch is not None:
                return batch
            return self.db.execute(
                "SELECT * FROM work w WHERE checked_at IS NULL AND due<=? AND lease_until<=? "
                "AND NOT EXISTS(SELECT 1 FROM omissions o WHERE o.kind='title' AND o.id=w.title_id AND o.tombstoned=1) "
                "AND NOT EXISTS(SELECT 1 FROM signal_pending p WHERE p.path=w.path AND p.failures<?) ORDER BY due,path LIMIT 1",
                (now, now, MAX_EXPECTED_MISSES),
            ).fetchone()

        def deferred_new():
            # Recent hints avoid a synchronous whole-series fanout by deferring
            # unrelated new descendants. Once due bootstrap work is exhausted,
            # fill that retained backlog instead of idling for a week. Failures
            # and targeted hints keep their explicit retry/cooldown deadlines.
            return self.db.execute(
                "SELECT * FROM work w WHERE checked_at IS NULL AND failures=0 AND due>? AND lease_until<=? "
                "AND NOT EXISTS(SELECT 1 FROM omissions o WHERE o.kind='title' AND o.id=w.title_id AND o.tombstoned=1) "
                "AND NOT EXISTS(SELECT 1 FROM signal_pending p WHERE p.path=w.path AND p.failures<?) ORDER BY due,path LIMIT 1",
                (now, now, MAX_EXPECTED_MISSES),
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
                "SELECT w.* FROM work w JOIN title_schedule s USING(title_id) "
                "WHERE w.checked_at IS NOT NULL AND w.lease_until<=? AND ("
                "(w.due<=? AND (w.checked_at<=? OR w.failures>0)) OR "
                "(w.failures=0 AND w.kind IN ('title','season') AND "
                "((s.changed_at>? AND w.checked_at<=?) OR w.checked_at<=(SELECT gap_since FROM signal_meta)))) "
                "AND NOT EXISTS(SELECT 1 FROM signal_pending p WHERE p.path=w.path AND p.failures<?) "
                "AND NOT EXISTS(SELECT 1 FROM omissions o WHERE o.kind='title' AND o.id=w.title_id AND o.tombstoned=1) "
                "ORDER BY CASE WHEN w.failures>0 THEN 0 WHEN w.kind IN ('title','season') AND s.changed_at>? THEN 1 ELSE 2 END,w.checked_at,w.path LIMIT 1",
                (
                    now,
                    now,
                    now - reconciliation_s,
                    now - 2592000,
                    now - active_s,
                    MAX_EXPECTED_MISSES,
                    now - 2592000,
                ),
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
            row = deferred_new()
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
        with atomic(self.db):
            row = self.db.execute(
                "SELECT * FROM signal_pending WHERE path=?", (work["path"],)
            ).fetchone()
            if row is None:
                if generation is not None:
                    # A concurrent newly observed variant must survive this old checkpoint.
                    self.db.execute(
                        "UPDATE work SET due=min(due,(SELECT due FROM signal_pending WHERE path=?)) WHERE path=? AND EXISTS(SELECT 1 FROM signal_pending WHERE path=?)",
                        (work["path"], work["path"], work["path"]),
                    )
                return
            if generation is None:
                # A normal historical detail recheck may resolve a terminal
                # obligation, but it must never consume an active hint it did
                # not claim.
                if row["failures"] < MAX_EXPECTED_MISSES:
                    return
            elif row["generation"] != generation:
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
            missing = sorted(set(expected) - observed)
            if success and checked == now and not missing:
                # Every advertised language is real. Drop the obligation (and
                # its anomaly) without claiming the feed window is complete:
                # coverage/gap_since and observation_gap stay historical.
                self.db.execute(
                    "DELETE FROM signal_pending WHERE path=?", (work["path"],)
                )
                self.db.execute(
                    "DELETE FROM quarantine WHERE kind=? AND digest=?",
                    (QUARANTINE_KIND, quarantine_digest(work["path"])),
                )
            elif success and row["failures"] + 1 >= MAX_EXPECTED_MISSES:
                # Never-observable expectation: keep the path, labels,
                # generation and first observation as durable evidence, but
                # release the active hint budget. Active claims/accounting
                # exclude this terminal row; a fresh advertised language can
                # reopen it.
                self.db.execute(
                    "INSERT INTO quarantine VALUES(?,?,?,?,?,0) "
                    "ON CONFLICT(digest) DO UPDATE SET old_count=excluded.old_count,new_count=excluded.new_count",
                    (
                        quarantine_digest(work["path"]),
                        QUARANTINE_KIND,
                        len(expected),
                        len(observed),
                        now,
                    ),
                )
                due = self.db.execute(
                    "SELECT due FROM work WHERE path=?", (work["path"],)
                ).fetchone()[0]
                terminal_due = max(due, now + TERMINAL_RETRY_S)
                self.db.execute(
                    "UPDATE work SET due=? WHERE path=?", (terminal_due, work["path"])
                )
                self.db.execute(
                    "UPDATE signal_pending SET failures=?,due=? WHERE path=?",
                    (MAX_EXPECTED_MISSES, terminal_due, work["path"]),
                )
                self.db.execute(
                    "UPDATE signal_meta SET coverage='gap',gap_since=coalesce(gap_since,?)",
                    (now,),
                )
                if missing:
                    self.db.execute(
                        "INSERT INTO observation_gap VALUES(?,?) ON CONFLICT(path) DO UPDATE SET unknown_languages=max(observation_gap.unknown_languages,excluded.unknown_languages)",
                        (work["path"], len(missing)),
                    )
            else:
                due = self.db.execute(
                    "SELECT due FROM work WHERE path=?", (work["path"],)
                ).fetchone()[0]
                # A feed can advertise a language that never appears on the
                # detail page. Retain the obligation without fetching that same
                # successful-but-incomplete page every minute indefinitely.
                delay = min(3600, 60 * 2 ** min(row["failures"], 6)) if success else 1
                retry_due = max(now + delay, due if not success else 0)
                self.db.execute(
                    "UPDATE work SET due=? WHERE path=?", (retry_due, work["path"])
                )
                self.db.execute(
                    "UPDATE signal_pending SET due=?,failures=failures+1 WHERE path=? AND generation=?",
                    (
                        retry_due,
                        work["path"],
                        row["generation"],
                    ),
                )
                self.db.execute(
                    "UPDATE signal_meta SET coverage='gap',gap_since=coalesce(gap_since,?)",
                    (now,),
                )
