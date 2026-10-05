"""Indexed metadata projection; worker scheduling/private tables are inaccessible."""

import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from catalog_core import query, schema
from catalog_core.json_codec import loads, require
from catalog_core.protocol import Request, Response, Row, Title, request_digest

from .read_catalog import lease


class CancelConnection:
    def __init__(self, db, interrupted):
        self.db, self.interrupted = db, interrupted

    def execute(self, sql, params=()):
        if self.interrupted():
            raise sqlite3.OperationalError("interrupted")
        return self.db.execute(sql, params)

    def set_progress_handler(self, predicate, steps):
        self.db.set_progress_handler(
            lambda: int(self.interrupted() or predicate()), steps
        )


class ReadStore:
    def __init__(self, db: sqlite3.Connection, metadata: dict) -> None:
        self.db, self.metadata = db, metadata
        self.providers = (metadata["provider"],)

    @contextmanager
    def acquire(self):
        yield {self.providers[0]: (self.db, self.metadata)}, None


def titles(db: sqlite3.Connection, ids: set[str]) -> list[Title]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    values = sorted(ids)
    result = []
    for row in db.execute(
        f"SELECT * FROM title WHERE title_id IN ({placeholders}) ORDER BY title_id",
        values,
    ):
        aliases = [
            r[0]
            for r in db.execute(
                "SELECT display_alias FROM alias WHERE title_id=? LIMIT 33",
                (row["title_id"],),
            )
        ]
        maps = [
            dict(r)
            for r in db.execute(
                "SELECT * FROM canonical_title WHERE title_id=?", (row["title_id"],)
            )
        ]
        result.append(Title(**dict(row), aliases=aliases, mappings=maps))
    return result


def execute(
    root: Path, request: Request, now: int, cancel: threading.Event | None = None
) -> Response:
    cancel = cancel or threading.Event()
    deadline = time.monotonic() + 2
    with lease(root):
        metadata = loads((root / "current.json").read_bytes(), 65536)
        require(metadata["provider"] == request.provider, "provider_unavailable")
        db = schema.connect(root / metadata["database"])
        try:

            def interrupted() -> int:
                return int(cancel.is_set() or time.monotonic() > deadline)

            db.set_progress_handler(interrupted, 1000)
            parsed = query.parse(request.params)
            rows, total, headers = [], 0, {}
            if request.operation == "titles":
                selected = (
                    set(query.candidates(db, parsed.text)) if parsed.text else set()
                )
                # Union here deliberately preserves ambiguous/conflicting matches.
                # Local corrections and intersection are applied by AniBridge.
                for namespace, value in parsed.ids.items():
                    selected.update(
                        r[0]
                        for r in db.execute(
                            "SELECT title_id FROM canonical_title WHERE namespace=? AND external_id=? LIMIT 201",
                            (namespace, value),
                        )
                    )
                require(len(selected) <= 200, "query_too_broad")
                title_rows = titles(db, selected)
                total = len(title_rows)
            else:
                selected = (
                    set(request.title_ids) if request.operation == "native" else None
                )
                parsed = replace(parsed, limit=request.limit, offset=request.offset)
                rows, total, headers = query.query(
                    ReadStore(CancelConnection(db, interrupted), metadata),
                    parsed,
                    now=now,
                    title_ids=selected,
                    languages={request.provider: set(request.languages)}
                    if request.operation == "recent"
                    else None,
                )
                db.set_progress_handler(interrupted, 1000)
                title_rows = titles(
                    db,
                    selected if selected is not None else {r["title_id"] for r in rows},
                )
            records = []
            for row in rows:
                maps = [
                    dict(r)
                    for r in db.execute(
                        "SELECT * FROM canonical_episode WHERE entity_id=?",
                        (row["entity_id"],),
                    )
                ]
                records.append(
                    Row(
                        **{
                            key: row[key]
                            for key in Row.model_fields
                            if key != "mappings"
                        },
                        mappings=maps,
                    )
                )
            require(not interrupted(), "query_deadline")
            response = Response(
                query_digest=request_digest(request),
                source_id=metadata["source_id"],
                provider=request.provider,
                revision=metadata["revision"],
                snapshot_digest=metadata["artifact"]["sqlite_sha256"],
                listing_checked_at=metadata["listing_checked_at"],
                total=total,
                offset=request.offset,
                mapping=headers.get("X-AniBridge-Mapping", "resolved"),
                rows=records,
                titles=title_rows,
            )
            response.check_request(request, metadata["source_id"])
            return response
        finally:
            db.close()
