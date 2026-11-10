"""Indexed metadata projection; worker scheduling/private tables are inaccessible."""

import sqlite3
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from catalog_core import query, schema
from catalog_core.json_codec import ContractError, loads, require
from catalog_core.protocol import Request, Response, Row, Title, request_digest

from .read_catalog import database_file, lease, provider_root


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


def titles(db: sqlite3.Connection, ids: set[str], provider: str) -> list[Title]:
    if not ids:
        return []
    placeholders = ",".join("?" for _ in ids)
    values = sorted(ids)
    rows = list(
        db.execute(
            f"SELECT * FROM title WHERE title_id IN ({placeholders}) ORDER BY title_id",
            values,
        )
    )
    if not rows:
        return []
    aliases: dict[str, list[str]] = defaultdict(list)
    # One grouped query replaces two lookups per title (400 round trips for a
    # 200-title discovery page). row_number keeps the existing 33-alias bound.
    for title_id, alias in db.execute(
        "SELECT title_id,display_alias FROM ("
        "SELECT title_id,display_alias,row_number() OVER "
        "(PARTITION BY title_id ORDER BY search_key) AS rank "
        f"FROM alias WHERE title_id IN ({placeholders})"
        ") WHERE rank<=33 ORDER BY title_id,rank",
        values,
    ):
        aliases[title_id].append(alias)
    mappings: dict[str, list[dict]] = defaultdict(list)
    for mapping in db.execute(
        f"SELECT * FROM canonical_title WHERE title_id IN ({placeholders}) ORDER BY title_id",
        values,
    ):
        mappings[mapping["title_id"]].append(dict(mapping))
    return [
        Title(
            **dict(row),
            provider=provider,
            aliases=aliases[row["title_id"]],
            mappings=mappings[row["title_id"]],
        )
        for row in rows
    ]


def execute(
    root: Path, request: Request, now: int, cancel: threading.Event | None = None
) -> Response:
    cancel = cancel or threading.Event()
    deadline = time.monotonic() + 2
    root = provider_root(root, request.provider)
    with lease(root):
        metadata = loads((root / "current.json").read_bytes(), 65536)
        require(metadata["provider"] == request.provider, "provider_unavailable")
        db = schema.connect(database_file(root, metadata))
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
                title_rows = titles(db, selected, request.provider)
                total = len(title_rows)
            else:
                selected = (
                    set(request.title_ids) if request.operation == "native" else None
                )
                entities = None
                if request.operation == "native" and request.season is not None:
                    # One indexed batch of canonical matches plus correction IDs;
                    # never fetch an entire long show's history to find one season.
                    terms = "ce.season=?"
                    values = [request.coordinate_namespace, request.season]
                    if request.episode is not None:
                        terms += " AND ce.episode=?"
                        values.append(request.episode)
                    placeholders = ",".join("?" for _ in selected)
                    entities = {
                        r[0]
                        for r in db.execute(
                            (
                                "SELECT e.entity_id FROM canonical_title_data ct JOIN title_data t USING(title_key) "
                                "JOIN canonical_episode_data ce USING(mapping_key) JOIN entity_data e USING(entity_key) "
                                f"WHERE ct.namespace=? AND {terms} AND t.title_id IN ({placeholders}) LIMIT 2001"
                            )
                            if metadata["catalog_schema_version"] == 2
                            else (
                                "SELECT ce.entity_id FROM canonical_episode ce JOIN canonical_title ct USING(mapping_id) "
                                f"WHERE ct.namespace=? AND {terms} AND ct.title_id IN ({placeholders}) LIMIT 2001"
                            ),
                            [*values, *sorted(selected)],
                        )
                    }
                    entities.update(request.include_entities)
                    require(len(entities) <= 2000, "query_too_broad")
                parsed = replace(parsed, limit=request.limit, offset=request.offset)
                try:
                    rows, total, headers = query.query(
                        ReadStore(CancelConnection(db, interrupted), metadata),
                        parsed,
                        now=now,
                        title_ids=selected,
                        entity_ids=entities,
                        max_releases=2000 if request.operation == "native" else None,
                        languages=(
                            None
                            if request.provider == "filmo.to" and not request.languages
                            else {request.provider: set(request.languages)}
                        )
                        if request.operation in {"recent", "native"}
                        else None,
                        offer_hosts=set(request.offer_hosts) or None,
                    )
                except sqlite3.OperationalError:
                    # A progress-handler abort is surfaced by SQLite as
                    # OperationalError; report the cooperative budget instead of
                    # a generic catalog outage.
                    if interrupted():
                        raise ContractError("query_deadline") from None
                    raise
                if (
                    request.operation == "native"
                    and request.season is not None
                    and total == 0
                ):
                    # No canonical association is not evidence of provider
                    # absence. Keep empty targeted batches explicitly unresolved.
                    headers["X-AniBridge-Mapping"] = "unresolved"
                db.set_progress_handler(interrupted, 1000)
                title_rows = titles(
                    db,
                    selected if selected is not None else {r["title_id"] for r in rows},
                    request.provider,
                )
            # Batch episode mappings too: a 500-row response previously issued
            # up to 500 tiny queries inside the 2-second SQL budget.
            episode_maps: dict[str, list[dict]] = defaultdict(list)
            entity_ids = {row["entity_id"] for row in rows}
            if entity_ids:
                marks = ",".join("?" for _ in entity_ids)
                for mapping in db.execute(
                    "SELECT * FROM canonical_episode "
                    f"WHERE entity_id IN ({marks}) "
                    "ORDER BY entity_id,season,episode",
                    sorted(entity_ids),
                ):
                    episode_maps[mapping["entity_id"]].append(dict(mapping))
            records = [
                Row(
                    **{
                        key: row.get(key)
                        if key in {"variant_anchor", "release_metadata"}
                        else row[key]
                        for key in Row.model_fields
                        if key != "mappings"
                    },
                    mappings=episode_maps[row["entity_id"]],
                )
                for row in rows
            ]
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
