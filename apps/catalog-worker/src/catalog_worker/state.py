"""Durable crawl checkpoints and immutable discovery history for one provider.

Artifact tables hold last-good observations. Scheduling, omissions and raw
diagnostics are private tables and are never copied wholesale to publication.
"""

import hashlib
import sqlite3
from pathlib import Path

from catalog_core import identity
from catalog_core.json_codec import dumps, require

from .adapters import adapter
from .aniworld import Page
from .state_migrations import initialize
from .transactions import atomic


class State:
    def __init__(self, filename: Path, provider: str) -> None:
        filename.parent.mkdir(parents=True, exist_ok=True)
        initialize(filename, provider)
        self.db = sqlite3.connect(filename)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA cache_size=-32768")
        self.db.execute("PRAGMA mmap_size=0")
        self.provider = provider

    def close(self) -> None:
        self.db.close()

    def meta(self) -> dict:
        return dict(self.db.execute("SELECT * FROM worker_meta").fetchone())

    def clock(self, now: int) -> int:
        previous = self.meta()["wall"]
        if now < previous - 300:
            with atomic(self.db):
                self.db.execute("UPDATE worker_meta SET state='clock_error'")
            raise ValueError("clock_error")
        now = max(now, previous)
        with atomic(self.db):
            self.db.execute("UPDATE worker_meta SET wall=?", (now,))
        return now

    def budget_delay(
        self, now: int, hourly: int, *, reconciliation: bool = False
    ) -> int:
        """Hourly exhaustion is durable deferral, separate from brief start spacing."""
        count, first = self.db.execute(
            "SELECT count(*),min(at) FROM request_start WHERE at>?", (now - 3600,)
        ).fetchone()
        delay = first + 3600 - now if count >= hourly else 0
        if reconciliation:
            count, first = self.db.execute(
                "SELECT count(*),min(at) FROM reconciliation_start WHERE at>?",
                (now - 3600,),
            ).fetchone()
            if count >= max(1, hourly // 5):
                delay = max(delay, first + 3600 - now)
        return delay

    def request_delay(
        self, now: int, interval: int, hourly: int, *, reconciliation: bool = False
    ) -> int:
        last = self.db.execute(
            "SELECT max(at) FROM request_start WHERE at>?", (now - 3600,)
        ).fetchone()[0]
        return max(
            0,
            (last or 0) + interval - now,
            self.budget_delay(now, hourly, reconciliation=reconciliation),
        )

    def defer(self, plan, now: int, seconds: int) -> None:
        """Release durable reservations without failure, gap or circuit evidence."""
        with atomic(self.db):
            if plan.work:
                self.db.execute(
                    "UPDATE work SET due=?,lease_until=0 WHERE path=?",
                    (now + seconds, plan.work["path"]),
                )
            elif plan.signal:
                self.db.execute(
                    "UPDATE signal_meta SET next_due=?,lease_until=0", (now + seconds,)
                )
            else:
                self.db.execute(
                    "UPDATE worker_meta SET next_listing=?", (now + seconds,)
                )
            if plan.circuit_lease is not None:
                self.db.execute(
                    "UPDATE worker_meta SET blocked_until=? WHERE blocked_until=?",
                    (now, plan.circuit_lease),
                )

    def success(self) -> None:
        # A real positive response interrupts the sustained-failure streak.
        self.db.execute("DELETE FROM transport_failure")
        self.db.execute("UPDATE worker_meta SET block_count=0 WHERE blocked_until=0")

    def allow_request(
        self, now: int, interval: int, hourly: int, *, reconciliation: bool = False
    ) -> bool:
        with atomic(self.db):
            self.db.execute("DELETE FROM request_start WHERE at<=?", (now - 3600,))
            self.db.execute(
                "DELETE FROM reconciliation_start WHERE at<=?", (now - 3600,)
            )
            if reconciliation and self.db.execute(
                "SELECT count(*) FROM reconciliation_start"
            ).fetchone()[0] >= max(1, hourly // 5):
                return False
            count, last = self.db.execute(
                "SELECT count(*),max(at) FROM request_start"
            ).fetchone()
            if count >= hourly or (last is not None and now - last < interval):
                return False
            self.db.execute("INSERT INTO request_start VALUES(?)", (now,))
            if reconciliation:
                self.db.execute("INSERT INTO reconciliation_start VALUES(?)", (now,))
            return True

    def _collapse(
        self, kind: str, old: int, new: int, candidate: object, now: int
    ) -> bool:
        if not old or new >= old * 0.9:
            return False
        digest = (
            candidate.digest()
            if hasattr(candidate, "digest")
            else hashlib.sha256(dumps(candidate)).hexdigest()
        )
        self.db.execute(
            "INSERT OR IGNORE INTO quarantine VALUES(?,?,?,?,?,0)",
            (digest, kind, old, new, now),
        )
        return not self.db.execute(
            "SELECT approved FROM quarantine WHERE digest=?", (digest,)
        ).fetchone()[0]

    def approve(self, digest: str) -> None:
        """Approve one inspected candidate, never a blanket anomaly bypass."""
        with atomic(self.db):
            require(
                self.db.execute(
                    "UPDATE quarantine SET approved=1 WHERE digest=?", (digest,)
                ).rowcount
                == 1,
                "unknown quarantine digest",
            )

    def _observe_absence(
        self, kind: str, previous: list[str], observed: set[str], now: int
    ) -> None:
        for record_id in previous:
            if record_id in observed:
                self.db.execute(
                    "DELETE FROM omissions WHERE kind=? AND id=?", (kind, record_id)
                )
            else:
                self.db.execute(
                    "INSERT INTO omissions(kind,id,first_missing,count) VALUES(?,?,?,1) ON CONFLICT(kind,id) DO UPDATE SET count=count+1",
                    (kind, record_id, now),
                )
                self.db.execute(
                    "UPDATE omissions SET tombstoned=1 WHERE kind=? AND id=? AND count>=3 AND first_missing<=?",
                    (kind, record_id, now - 172800),
                )

    def listing(
        self, page: Page, now: int, interval: int = 14400, accepted=lambda: None
    ) -> bool:
        # A TEMP table bounds Python memory and lets omission checks use indexes.
        with atomic(self.db):
            self.db.execute(
                "CREATE TEMP TABLE IF NOT EXISTS observed(id TEXT PRIMARY KEY)"
            )
            self.db.execute("DELETE FROM observed")
            for link in page.links:
                self.db.execute(
                    "INSERT OR IGNORE INTO observed VALUES(?)",
                    (identity.title_id(self.provider, link.path),),
                )
            old = self.db.execute(
                "SELECT count(*) FROM title WHERE title_id NOT IN (SELECT id FROM omissions WHERE kind='title' AND tombstoned=1)"
            ).fetchone()[0]
            if self._collapse(
                "listing",
                old,
                len(page.links),
                page.links
                if hasattr(page.links, "digest")
                else [link.path for link in page.links],
                now,
            ):
                self.db.execute(
                    "UPDATE worker_meta SET state='parser_error',next_listing=?",
                    (now + 86400,),
                )
                accepted()
                return False
            for link in page.links:
                self.discover(link, now)
            self.db.execute(
                "INSERT INTO omissions(kind,id,first_missing,count) SELECT 'title',title_id,?,1 FROM title WHERE title_id NOT IN (SELECT id FROM observed) ON CONFLICT(kind,id) DO UPDATE SET count=count+1",
                (now,),
            )
            self.db.execute(
                "UPDATE omissions SET tombstoned=1 WHERE kind='title' AND count>=3 AND first_missing<=? AND confirmed_404=1",
                (now - 172800,),
            )
            self.db.execute("UPDATE catalog SET listing_checked_at=?", (now,))
            self.db.execute(
                "UPDATE worker_meta SET listing_checked_at=?,next_listing=?,state=CASE WHEN blocked_until>? THEN 'blocked' ELSE 'partial' END,dirty=1",
                (now, now + interval, now),
            )
            accepted()
        return True

    def discover(self, link, now: int) -> str:
        """Admit a positive title hint without treating other titles as absent."""
        tid = identity.title_id(self.provider, link.path)
        movie = self.provider == "megakino" and link.path.startswith("/films/")
        media_type = (
            "movie" if movie else "unknown" if self.provider == "megakino" else "series"
        )
        update = (
            "DO NOTHING"
            if self.provider == "megakino"
            else "DO UPDATE SET display_title=excluded.display_title,search_key=excluded.search_key"
        )
        self.db.execute(
            "INSERT INTO title VALUES(?,?,?,?,?,?,NULL,?,?,'pending') ON CONFLICT(title_id) "
            + update,
            (
                tid,
                link.path,
                adapter(self.provider).TITLE.fullmatch(link.path)[2]
                if self.provider == "megakino"
                else link.path.rsplit("/", 1)[1],
                link.name,
                identity.search_key(link.name),
                media_type,
                link.path,
                now,
            ),
        )
        self.db.execute(
            "INSERT INTO title_schedule VALUES(?,?,?,?) ON CONFLICT(title_id) DO UPDATE SET listed_at=excluded.listed_at",
            (tid, now, now, now),
        )
        for alias in link.aliases:
            self.db.execute(
                "INSERT INTO alias VALUES(?,?,?) ON CONFLICT(title_id,search_key) DO UPDATE SET display_alias=excluded.display_alias",
                (tid, identity.search_key(alias), alias),
            )
        # Existing due work and mapping eligibility survive unchanged listings.
        self.db.execute(
            "INSERT OR IGNORE INTO work(path,title_id,kind,due) VALUES(?,?,'title',?)",
            (link.path, tid, now),
        )
        self.db.execute("DELETE FROM omissions WHERE kind='title' AND id=?", (tid,))
        return tid

    def claim(
        self,
        now: int,
        lease_s: int = 120,
        *,
        incremental: bool = False,
        reconciliation_s: int = 604800,
        hourly: int = 1200,
    ) -> dict | None:
        """Reserve every fifth slot for the oldest new/historical work.

        Active work otherwise follows oldest due first, after undiscovered pages.
        The persistent slot counter prevents restarts from starving history.
        """
        with atomic(self.db):
            slot = self.db.execute("SELECT slot FROM scheduler").fetchone()[0]
            base = """SELECT w.* FROM work w JOIN title_schedule s USING(title_id)
                WHERE w.due<=? AND w.lease_until<=?
                AND NOT EXISTS (SELECT 1 FROM omissions o WHERE o.kind='title' AND o.id=w.title_id AND o.tombstoned=1)
                AND (?<>'megakino' OR w.path LIKE '/films/%')
                """
            # Separate indexed selections preserve new → active → historical
            # priority without sorting the whole due queue by a computed class.
            bands = ("<=", ">") if slot % 5 == 4 else (">", "<=")
            order = " ORDER BY w.due,w.path LIMIT 1"
            if incremental:
                from .signals import Signals

                row = Signals(self).claim(now, slot, lease_s, reconciliation_s, hourly)
                if row is not None:
                    self.db.execute("UPDATE scheduler SET slot=slot+1")
                    return row
                return None
            row = self.db.execute(
                base + " AND w.checked_at IS NULL" + order, (now, now, self.provider)
            ).fetchone()
            for comparison in bands:
                if row is not None:
                    break
                row = self.db.execute(
                    base
                    + f" AND w.checked_at IS NOT NULL AND s.changed_at{comparison}?"
                    + order,
                    (now, now, self.provider, now - 2592000),
                ).fetchone()
            if row is None:
                return None
            self.db.execute("UPDATE scheduler SET slot=slot+1")
            self.db.execute(
                "UPDATE work SET lease_until=? WHERE path=?",
                (now + lease_s, row["path"]),
            )
            return dict(row)

    def claim_title(self, title_id: str, now: int, lease_s: int = 120) -> dict | None:
        """Bounded selected-title work also works inside a normal bootstrap ledger."""
        with atomic(self.db):
            if self.meta()["blocked_until"] > now:
                return None
            row = self.db.execute(
                "SELECT * FROM work WHERE title_id=? AND due<=? AND lease_until<=? ORDER BY due,path LIMIT 1",
                (title_id, now, now),
            ).fetchone()
            if row is None:
                return None
            self.db.execute(
                "UPDATE work SET lease_until=? WHERE path=?",
                (now + lease_s, row["path"]),
            )
            return dict(row)

    def detail(
        self,
        work: dict,
        page: Page,
        now: int,
        interval: int = 14400,
        historical_interval: int = 604800,
    ) -> None:
        tid = work["title_id"]
        fingerprint = hashlib.sha256(
            dumps(
                {
                    "title": page.title,
                    "links": [(link.path, link.name) for link in page.links],
                    "languages": page.languages,
                    "episode_title": page.episode_title,
                    "episode_aliases": page.episode_aliases,
                    "rows": [
                        (r.path, r.title, r.aliases, r.languages, r.unknown_languages)
                        for r in page.episodes
                    ],
                    "year": page.year,
                    "explicit_imdb": page.explicit_imdb,
                    "aliases": page.aliases,
                }
            )
        ).hexdigest()
        with atomic(self.db):
            movie = self.provider == "megakino" and work["path"].startswith("/films/")
            if work["kind"] == "episode" or movie:
                eid = identity.entity_id(self.provider, work["path"])
                season, episode = (
                    (None, None)
                    if movie
                    else adapter(self.provider).coordinates(work["path"])
                )
                old = self.db.execute(
                    "SELECT count(*) FROM release WHERE entity_id=?", (eid,)
                ).fetchone()[0]
                if not work.get("batch") and self._collapse(
                    "languages", old, len(page.languages), [eid, page.languages], now
                ):
                    self.db.execute(
                        "UPDATE title SET detail_status='stale' WHERE title_id=?",
                        (tid,),
                    )
                    self.db.execute(
                        "UPDATE work SET lease_until=0,due=? WHERE path=?",
                        (now + 86400, work["path"]),
                    )
                    self.db.execute("UPDATE worker_meta SET state='parser_error'")
                    return
                self.db.execute(
                    "INSERT INTO entity VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(entity_id) DO UPDATE SET display_title=coalesce(excluded.display_title,entity.display_title),observed_at=excluded.observed_at",
                    (
                        eid,
                        tid,
                        work["path"],
                        "movie" if movie else "episode",
                        season,
                        episode,
                        page.title if movie else page.episode_title,
                        work["path"],
                        now,
                    ),
                )
                if page.episode_title:
                    # Replace source aliases only with a complete named observation.
                    self.db.execute(
                        "DELETE FROM entity_alias WHERE entity_id=?", (eid,)
                    )
                    for alias in page.episode_aliases:
                        self.db.execute(
                            "INSERT OR IGNORE INTO entity_alias VALUES(?,?,?)",
                            (eid, identity.search_key(alias), alias),
                        )
                # A genuinely new positive observation extends the active window.
                new_languages = set(page.languages) - {
                    row[0]
                    for row in self.db.execute(
                        "SELECT language FROM release WHERE entity_id=?", (eid,)
                    )
                }
                if new_languages:
                    self.db.execute(
                        "UPDATE title_schedule SET changed_at=? WHERE title_id=?",
                        (now, tid),
                    )
                for language in page.languages:
                    rid = identity.release_id(self.provider, eid, language)
                    self.db.execute(
                        "INSERT INTO release VALUES(?,?,?,?,?) ON CONFLICT(release_id) DO UPDATE SET observed_at=max(release.observed_at,excluded.observed_at)",
                        (rid, eid, language, now, now),
                    )
                    self.db.execute(
                        "DELETE FROM omissions WHERE kind='release' AND id=?", (rid,)
                    )
                if not work.get("batch"):
                    self._observe_absence(
                        "release",
                        [
                            r[0]
                            for r in self.db.execute(
                                "SELECT release_id FROM release WHERE entity_id=?",
                                (eid,),
                            )
                        ],
                        {
                            identity.release_id(self.provider, eid, language)
                            for language in page.languages
                        },
                        now,
                    )
            else:
                parent = self.db.execute(
                    "SELECT path FROM title WHERE title_id=?", (tid,)
                ).fetchone()[0]
                if work["kind"] == "season":
                    old_entities = [
                        r[0]
                        for r in self.db.execute(
                            "SELECT entity_id FROM entity WHERE title_id=? AND path LIKE ?",
                            (tid, work["path"] + "/%"),
                        )
                    ]
                    observed = {
                        identity.entity_id(self.provider, link.path)
                        for link in page.links
                        if adapter(self.provider).EPISODE.fullmatch(link.path)
                        and link.path.startswith(work["path"] + "/")
                    }
                    if self._collapse(
                        "entities",
                        len(old_entities),
                        len(observed),
                        sorted(observed),
                        now,
                    ):
                        self.db.execute("UPDATE worker_meta SET state='parser_error'")
                        self.db.execute(
                            "UPDATE work SET lease_until=0,due=? WHERE path=?",
                            (now + 86400, work["path"]),
                        )
                        self.db.execute(
                            "UPDATE title SET detail_status='stale' WHERE title_id=?",
                            (tid,),
                        )
                        return
                    self._observe_absence("entity", old_entities, observed, now)
                for link in page.links:
                    if not link.path.startswith(parent + "/"):
                        continue
                    if (
                        work.get("targeted")
                        and not self.db.execute(
                            "SELECT 1 FROM signal_pending WHERE path=?", (link.path,)
                        ).fetchone()
                    ):
                        kind = (
                            "episode"
                            if adapter(self.provider).EPISODE.fullmatch(link.path)
                            else "season"
                        )
                        self.db.execute(
                            "INSERT OR IGNORE INTO work(path,title_id,kind,due) VALUES(?,?,?,?)",
                            (link.path, tid, kind, now + historical_interval),
                        )
                        continue
                    kind = (
                        "episode"
                        if adapter(self.provider).EPISODE.fullmatch(link.path)
                        else "season"
                    )
                    self.db.execute(
                        "INSERT OR IGNORE INTO work(path,title_id,kind,due) VALUES(?,?,?,?)",
                        (link.path, tid, kind, now),
                    )
            if work["kind"] == "season":
                from .batch import admit

                admit(self, work, page, now, interval, historical_interval)
                self.db.execute(
                    "INSERT INTO season_batch_checkpoint VALUES(?,?) ON CONFLICT(path) DO UPDATE SET checked_at=excluded.checked_at",
                    (work["path"], now),
                )
            if work["kind"] == "title":
                if page.title:
                    self.db.execute(
                        "UPDATE title SET display_title=?,search_key=? WHERE title_id=?",
                        (page.title, identity.search_key(page.title), tid),
                    )
                self.db.execute(
                    "UPDATE title SET year=? WHERE title_id=?", (page.year, tid)
                )
                for alias in page.aliases:
                    self.db.execute(
                        "INSERT INTO alias VALUES(?,?,?) ON CONFLICT(title_id,search_key) DO UPDATE SET display_alias=excluded.display_alias",
                        (tid, identity.search_key(alias), alias),
                    )
                self.db.execute(
                    "INSERT INTO mapping_input(title_id,explicit_imdb) VALUES(?,?) ON CONFLICT(title_id) DO UPDATE SET explicit_imdb=excluded.explicit_imdb",
                    (tid, page.explicit_imdb),
                )
            if fingerprint != work.get("fingerprint"):
                self.db.execute(
                    "UPDATE mapping_input SET next_due=0 WHERE title_id=?", (tid,)
                )
            self.db.execute(
                "INSERT INTO observation_gap VALUES(?,?) ON CONFLICT(path) DO UPDATE SET unknown_languages=excluded.unknown_languages",
                (work["path"], page.unknown_languages),
            )
            changed_at = self.db.execute(
                "SELECT changed_at FROM title_schedule WHERE title_id=?", (tid,)
            ).fetchone()[0]
            cadence = interval if changed_at > now - 2592000 else historical_interval
            if work.get("incremental"):
                cadence = historical_interval
            self.db.execute(
                "UPDATE work SET checked_at=?,due=?,lease_until=0,failures=0,fingerprint=? WHERE path=?",
                (now, now + cadence, fingerprint, work["path"]),
            )
            pending = self.db.execute(
                "SELECT 1 FROM work w LEFT JOIN observation_gap g USING(path) WHERE title_id=? AND (checked_at IS NULL OR failures>0 OR coalesce(g.unknown_languages,0)>0) LIMIT 1",
                (tid,),
            ).fetchone()
            self.db.execute(
                "UPDATE title SET observed_at=?,detail_status=? WHERE title_id=?",
                (
                    now,
                    "partial" if pending or page.unknown_languages else "complete",
                    tid,
                ),
            )
            self.db.execute(
                "UPDATE worker_meta SET dirty=1,state=CASE WHEN blocked_until>? THEN 'blocked' WHEN state IN ('parser_error','clock_error','storage_full') THEN state ELSE 'partial' END",
                (now,),
            )

    def failure(
        self, work: dict | None, outcome: str, now: int, retry_after: int | None = None
    ) -> None:
        from .retry import policy

        meta = self.meta()
        blocked, count = meta["blocked_until"], meta["block_count"]
        attempts = work["failures"] if work else count
        delay, state = policy(outcome, attempts, count, retry_after)
        with atomic(self.db):
            if outcome in ("challenge_or_block", "rate_limited"):
                blocked, count = max(blocked, now + delay), count + 1
            elif outcome == "transport_failure":
                self.db.execute(
                    "DELETE FROM transport_failure WHERE at<?", (now - 120,)
                )
                self.db.execute("INSERT INTO transport_failure VALUES(?)", (now,))
                failures, oldest = self.db.execute(
                    "SELECT count(*),min(at) FROM transport_failure"
                ).fetchone()
                # Eight consecutive real failures spanning >=30s establish more
                # than one unlucky page. Parser/admission failures never enter.
                if failures >= 8 and now - oldest >= 30:
                    circuit, _ = policy("circuit", 0, count, None)
                    blocked, count = max(blocked, now + circuit), count + 1
            self.db.execute(
                "UPDATE worker_meta SET state=?,blocked_until=?,block_count=?",
                (state, blocked, count),
            )
            if work:
                self.db.execute(
                    "UPDATE work SET due=?,lease_until=0,failures=failures+1 WHERE path=?",
                    (now + delay, work["path"]),
                )
                self.db.execute(
                    "UPDATE title SET detail_status='stale' WHERE title_id=?",
                    (work["title_id"],),
                )
                if outcome == "not_found" and work["kind"] == "title":
                    self.db.execute(
                        "UPDATE omissions SET confirmed_404=1 WHERE kind='title' AND id=?",
                        (work["title_id"],),
                    )
            else:
                self.db.execute("UPDATE worker_meta SET next_listing=?", (now + delay,))
