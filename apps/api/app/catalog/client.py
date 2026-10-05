"""One qBittorrent projection and durable alias-removal intents for catalog jobs."""

import json
from collections.abc import Iterator
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from .jobs import JobError, Jobs


def epoch(value: str | None) -> int:
    if not value:
        return 0
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())


def hash_values(hashes: str) -> list[str] | None:
    if hashes == "all":
        return None
    values = hashes.split("|")
    if not 1 <= len(values) <= 100 or any(
        len(value) != 40 or any(c not in "0123456789abcdefABCDEF" for c in value)
        for value in values
    ):
        raise JobError("invalid_request", 400)
    return [value.lower() for value in values]


class ClientJobs:
    def __init__(self, jobs: Jobs, public_root: str | None = None) -> None:
        self.jobs, self.public_root = jobs, public_root

    def alias_batches(
        self, hashes: str = "all", *, durable: bool = True, category: str | None = None
    ) -> Iterator[list[dict]]:
        """Read ordered alias pages; no reader remains leased across a yield."""
        values = hash_values(hashes)
        after = ""
        while True:
            where = (
                "c.hash>? AND "
                + ("" if durable else "NOT ")
                + "EXISTS (SELECT 1 FROM durable_request d WHERE d.job_id=c.job_id)"
            )
            params = [after]
            if values is not None:
                where += " AND c.hash IN (" + ",".join("?" for _ in values) + ")"
                params.extend(values)
            if category is not None:
                where += " AND coalesce(c.category,'')=?"
                params.append(category)
            with closing(self.jobs.db()) as db:
                batch = [
                    dict(row)
                    for row in db.execute(
                        f"SELECT c.* FROM clienttask c WHERE {where} ORDER BY c.hash LIMIT 100",
                        params,
                    )
                ]
            if not batch:
                return
            after = batch[-1]["hash"]
            yield batch

    def aliases(self, hashes: str = "all") -> list[dict]:
        """Small-selection compatibility helper; runtime history uses batches."""
        return [row for batch in self.alias_batches(hashes) for row in batch]

    def views(
        self, *, durable: bool = True, category: str | None = None
    ) -> Iterator[dict]:
        for batch in self.alias_batches(durable=durable, category=category):
            with closing(self.jobs.db()) as db:
                projected = []
                for alias in batch:
                    record = db.execute(
                        "SELECT * FROM job WHERE id=?", (alias["job_id"],)
                    ).fetchone()
                    if durable:
                        projected.append(self.view(alias, dict(record)))
                    else:
                        from app.api.qbittorrent.torrents import torrent_info_record

                        legacy = dict(alias)
                        for name in ("added_on", "completion_on"):
                            if legacy[name] is not None:
                                legacy[name] = datetime.fromisoformat(legacy[name])
                        projected.append(
                            torrent_info_record(
                                SimpleNamespace(**legacy),
                                SimpleNamespace(**dict(record)) if record else None,
                            )
                        )
            yield from projected

    def has_other_alias(self, job: str, requested: list[str] | set[str]) -> bool:
        with closing(self.jobs.db()) as db:
            return bool(
                db.execute(
                    "SELECT 1 FROM clienttask WHERE job_id=? AND hash NOT IN ("
                    + ",".join("?" for _ in requested)
                    + ") LIMIT 1",
                    [job, *requested],
                ).fetchone()
            )

    def job_batches(self, hashes: str) -> Iterator[list[str]]:
        """Select at most 100 distinct jobs per read without loading history."""
        values = hash_values(hashes)
        after = ""
        while True:
            where = "c.job_id=d.job_id"
            params = [after]
            if values is not None:
                where += " AND c.hash IN (" + ",".join("?" for _ in values) + ")"
                params.extend(values)
            with closing(self.jobs.db()) as db:
                batch = [
                    row[0]
                    for row in db.execute(
                        "SELECT d.job_id FROM durable_request d WHERE d.job_id>? "
                        f"AND EXISTS (SELECT 1 FROM clienttask c WHERE {where}) "
                        "ORDER BY d.job_id LIMIT 100",
                        params,
                    )
                ]
            if not batch:
                return
            after = batch[-1]
            # Release the read connection before callers commit transitions.
            yield batch

    def transition(self, hashes: str, action: str, now: int) -> None:
        for batch in self.job_batches(hashes):
            for job in batch:
                self.jobs.action(job, action, now, include_hashes=False)

    def view(self, alias: dict, row: dict | None = None) -> dict:
        if row is None:
            row = self.jobs.get(alias["job_id"], include_hashes=False)
        projection = self.jobs.project(row)
        content = projection["content_path"] or ""
        save = alias["save_path"] or str(self.jobs.download_dir)
        if content:
            save = str(Path(content).parent)
        if self.public_root:

            def public(path):
                relative = Path(path).resolve().relative_to(self.jobs.download_dir)
                return str(Path(self.public_root) / relative)

            save = public(save)
            content = public(content) if content else ""
        return {
            **projection,
            "hash": alias["hash"],
            "name": alias["name"],
            "category": alias["category"] or "",
            "save_path": save,
            "content_path": content,
            "completion_on": epoch(row["updated_at"])
            if row["status"] == "completed"
            else 0,
            "added_on": epoch(alias["added_on"]),
            "downloaded": row["downloaded_bytes"] or 0,
            "upspeed": 0,
            "num_seeds": 0,
            "num_leechs": 0,
        }

    def remove(self, hashes: str, delete_files: bool, now: int) -> None:
        for aliases in self.alias_batches(hashes):
            grouped: dict[str, list[str]] = {}
            for alias in aliases:
                grouped.setdefault(alias["job_id"], []).append(alias["hash"])
            with closing(self.jobs.db()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                for job, submitted in grouped.items():
                    body = json.dumps(
                        {
                            "job_id": job,
                            "hashes": submitted,
                            "delete_files": delete_files,
                        }
                    )
                    db.execute(
                        "INSERT INTO catalog_task VALUES(?, 'remove_aliases', 'queued', ?, 1, ?, ?)",
                        (str(uuid4()), body, now, now),
                    )
            # Each bounded intent survives a crash before cancellation. A job
            # spanning several intents is cancelled when its final alias settles.
            for job, submitted in grouped.items():
                if not self.has_other_alias(job, submitted):
                    self.jobs.action(job, "cancel", now, include_hashes=False)

    def settle_removals(self, running: set[str], now: int) -> None:
        with closing(self.jobs.db()) as db:
            tasks = [
                dict(row)
                for row in db.execute(
                    "SELECT * FROM catalog_task WHERE type='remove_aliases' AND state='queued' ORDER BY created_at LIMIT 100"
                )
            ]
        for task in tasks:
            body = json.loads(task["body"])
            job_id, requested = body["job_id"], set(body["hashes"])
            job = self.jobs.get(job_id, include_hashes=False)
            final_alias = not self.has_other_alias(job_id, requested)
            if final_alias:
                # Capture output before cancellation clears completion exposure.
                self.jobs.action(job_id, "cancel", now, include_hashes=False)
                if job_id in running:
                    continue
                self.jobs.settle_cancel(job_id, now)
            with closing(self.jobs.db()) as db, db:
                db.execute("BEGIN IMMEDIATE")
                other = db.execute(
                    "SELECT 1 FROM clienttask WHERE job_id=? AND hash NOT IN ("
                    + ",".join("?" for _ in requested)
                    + ") LIMIT 1",
                    [job_id, *requested],
                ).fetchone()
                if not other and body["delete_files"] and job["result_path"]:
                    target = Path(job["result_path"])
                    if not target.is_symlink() and target.resolve().is_relative_to(
                        self.jobs.download_dir
                    ):
                        target.unlink(missing_ok=True)
                for value in requested:
                    db.execute(
                        "DELETE FROM grab_alias WHERE hash=? AND job_id=?",
                        (value, job_id),
                    )
                    db.execute(
                        "DELETE FROM clienttask WHERE hash=? AND job_id=?",
                        (value, job_id),
                    )
                db.execute(
                    "UPDATE catalog_task SET state='succeeded',version=version+1,updated_at=? WHERE id=?",
                    (now, task["id"]),
                )
