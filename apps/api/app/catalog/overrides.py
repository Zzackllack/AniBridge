"""Local operator corrections; writes never resolve a canonical or provider URL."""

import hashlib
import json
import sqlite3
import time
from contextlib import closing, contextmanager
from uuid import UUID, uuid4

from catalog_core.identity import validate_external_id
from catalog_core.json_codec import dumps, fields, integer, require

from .management_auth import ManagementError
from .management_schema import bump
from .storage import writable


@contextmanager
def bounded(catalogs, db):
    """Use the search SQL budget for local management reads and writes too."""
    deadline = time.monotonic() + 2
    connections = [db, *(value[0] for value in catalogs.values())]
    for connection in connections:
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
    try:
        yield
    except sqlite3.OperationalError:
        # Never return raw SQLite messages or paths through the management API.
        raise ManagementError(
            "temporarily_unavailable", 503, "Local state is busy", True
        ) from None
    finally:
        for connection in connections:
            connection.set_progress_handler(None, 0)


def fingerprint(catalog, body: dict) -> str | None:
    title = catalog.execute(
        "SELECT title_id,identity_anchor,media_type,path FROM title WHERE title_id=?",
        (body["title_id"],),
    ).fetchone()
    if title is None:
        return None
    entity = None
    if body["entity_id"] is not None:
        entity = catalog.execute(
            "SELECT entity_id,title_id,identity_anchor,kind,native_season,native_episode,path FROM entity WHERE entity_id=? AND title_id=?",
            (body["entity_id"], body["title_id"]),
        ).fetchone()
        if entity is None or entity["kind"] != body["entity_kind"]:
            return None
    return hashlib.sha256(
        dumps([tuple(title), tuple(entity) if entity else None])
    ).hexdigest()


def effective_title(
    db, catalog, provider: str, title: str, namespace: str
) -> str | None:
    # Namespace-specific override beats that namespace's published title map.
    for row in db.execute(
        "SELECT body FROM catalog_override WHERE provider=? AND title_id=? AND namespace=? AND (entity_id IS NULL OR json_extract(body,'$.entity_kind')='movie')",
        (provider, title, namespace),
    ):
        body = json.loads(row[0])
        if (
            body["enabled"]
            and body["fingerprint"] == fingerprint(catalog, body)
            and not assignment_conflict(catalog, body)
        ):
            return body["target"]["external_id"]
    row = catalog.execute(
        "SELECT external_id FROM canonical_title WHERE title_id=? AND namespace=?",
        (title, namespace),
    ).fetchone()
    return row[0] if row else None


def assignment_conflict(catalog, body: dict) -> bool:
    """A correction cannot steal another published title or episode identity."""
    target = body["target"]
    if catalog.execute(
        "SELECT 1 FROM canonical_title WHERE namespace=? AND external_id=? AND title_id<>? LIMIT 1",
        (target["namespace"], target["external_id"], body["title_id"]),
    ).fetchone():
        return True
    return (
        body["entity_kind"] == "episode"
        and catalog.execute(
            "SELECT 1 FROM canonical_episode ce JOIN canonical_title ct USING(mapping_id) WHERE ct.namespace=? AND ct.external_id=? AND ce.season=? AND ce.episode=? AND ce.entity_id<>? LIMIT 1",
            (
                target["namespace"],
                target["external_id"],
                target["season"],
                target["episode"],
                body["entity_id"],
            ),
        ).fetchone()
        is not None
    )


def resolution(body: dict, db, catalog) -> tuple[str, str | None]:
    """Resolve status from the same leased snapshot used by search."""
    conflict = None
    if catalog is None or body["fingerprint"] != fingerprint(catalog, body):
        conflict = "entity_changed_or_missing"
    elif assignment_conflict(catalog, body):
        conflict = "canonical_assignment_conflict"
    elif (
        body["entity_kind"] == "episode"
        and effective_title(
            db, catalog, body["provider"], body["title_id"], body["target"]["namespace"]
        )
        != body["target"]["external_id"]
    ):
        conflict = "title_mapping_conflict"
    return (
        "disabled" if not body["enabled"] else "conflict" if conflict else "active",
        conflict if body["enabled"] else None,
    )


def reconcile(db, catalog, provider: str, now: int) -> None:
    """Persist status transitions with versions in the pointer/write transaction."""
    if catalog is not None:
        from catalog_core.identity import PROVIDERS

        from .refresh_view import observed

        catalog = observed(
            db, catalog, provider, sorted(PROVIDERS).index(provider), now
        )
    for row in db.execute(
        "SELECT * FROM catalog_override WHERE provider=?", (provider,)
    ):
        body = json.loads(row["body"])
        current = list(resolution(body, db, catalog))
        if body.get("resolution") != current:
            body["resolution"] = current
            db.execute(
                "UPDATE catalog_override SET body=?,version=version+1,updated_at=? WHERE id=?",
                (dumps(body).decode(), now, row["id"]),
            )


def resource(row, db, catalogs) -> dict:
    body = json.loads(row["body"])
    catalog = catalogs.get(row["provider"])
    state, conflict = resolution(body, db, catalog[0] if catalog else None)
    return {
        key: value
        for key, value in body.items()
        if key not in ("fingerprint", "resolution")
    } | {
        "id": row["id"],
        "version": row["version"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "provenance": "local_operator",
        "status": state,
        "conflict_reason": conflict,
    }


class Overrides:
    def __init__(self, store) -> None:
        self.store = store

    def validate(
        self, body: dict, db, catalogs, *, exclude=None, retained=None
    ) -> dict:
        try:
            fields(
                body,
                {
                    "provider",
                    "entity_kind",
                    "title_id",
                    "entity_id",
                    "target",
                    "reason",
                    "enabled",
                },
            )
            require(
                type(body["provider"]) is str
                and body["provider"] in self.store.providers,
                "provider",
            )
            require(body["entity_kind"] in ("title", "episode", "movie"), "kind")
            require(
                type(body["title_id"]) is str and len(body["title_id"]) == 64,
                "title ID",
            )
            require(
                body["entity_id"] is None
                if body["entity_kind"] == "title"
                else type(body["entity_id"]) is str and len(body["entity_id"]) == 64,
                "entity ID",
            )
            fields(body["target"], {"namespace", "external_id", "season", "episode"})
            target = body["target"]
            validate_external_id(target["namespace"], target["external_id"])
            if body["entity_kind"] == "episode":
                require(target["namespace"] in ("tvdb", "tmdb-tv"), "episode namespace")
                integer(target["season"], 0, 2**31 - 1)
                integer(target["episode"], 1, 2**31 - 1)
            else:
                require(
                    target["season"] is None and target["episode"] is None,
                    "coordinates",
                )
            require(
                type(body["reason"]) is str
                and bool(body["reason"].strip())
                and len(body["reason"].encode()) <= 1000,
                "reason",
            )
            require(type(body["enabled"]) is bool, "enabled")
            # Disabling or annotating a suspended correction must remain possible
            # even after its provider identity disappears. Re-enabling revalidates.
            if (
                retained is not None
                and not body["enabled"]
                and body["target"] == retained["target"]
            ):
                return {**body, "fingerprint": retained["fingerprint"]}
            current = catalogs.get(body["provider"])
            require(current is not None, "catalog")
            catalog = current[0]
            digest = fingerprint(catalog, body)
            require(digest is not None, "unknown identity")
            kind = catalog.execute(
                "SELECT media_type FROM title WHERE title_id=?", (body["title_id"],)
            ).fetchone()[0]
            require(kind in ("movie", "series"), "unknown media type")
            require(
                target["namespace"]
                in (
                    ("tmdb-movie", "imdb")
                    if kind == "movie"
                    else ("tvdb", "tmdb-tv", "imdb")
                ),
                "namespace/type",
            )
            if body["entity_kind"] == "episode":
                require(
                    effective_title(
                        db,
                        catalog,
                        body["provider"],
                        body["title_id"],
                        target["namespace"],
                    )
                    == target["external_id"],
                    "consistent title mapping required",
                )
        except ValueError, TypeError, KeyError:
            raise ManagementError(
                "validation_error", 422, "Invalid override identity, target or fields"
            ) from None
        if body["enabled"]:
            for other in db.execute(
                "SELECT id,body FROM catalog_override WHERE provider=? AND namespace=?",
                (body["provider"], target["namespace"]),
            ):
                saved = json.loads(other["body"])
                if other["id"] == exclude or not saved["enabled"]:
                    continue
                same_identity = (
                    saved["title_id"],
                    saved["entity_id"] if saved["entity_kind"] == "episode" else None,
                ) == (
                    body["title_id"],
                    body["entity_id"] if body["entity_kind"] == "episode" else None,
                )
                same_assignment = saved["target"] == target and (
                    saved["entity_kind"] == "episode"
                ) == (body["entity_kind"] == "episode")
                if same_identity or same_assignment:
                    raise ManagementError(
                        "conflict",
                        409,
                        "An enabled override already owns this identity or assignment",
                    )
            if assignment_conflict(catalog, body):
                raise ManagementError(
                    "conflict", 409, "Canonical assignment belongs to another identity"
                )
        return {**body, "fingerprint": digest}

    def list(self, provider=None, entity_id=None, limit=50, offset=0) -> dict:
        try:
            integer(limit, 1, 100)
            integer(offset, 0, 10000)
            require(provider is None or provider in self.store.providers, "provider")
            require(
                entity_id is None
                or (
                    len(entity_id) == 64
                    and all(c in "0123456789abcdef" for c in entity_id)
                ),
                "entity ID",
            )
        except ValueError, TypeError:
            raise ManagementError(
                "invalid_request", 400, "Invalid override filters"
            ) from None
        with self.store.acquire() as (catalogs, db), bounded(catalogs, db):
            where, values = [], []
            for key, value in (("provider", provider), ("entity_id", entity_id)):
                if value is not None:
                    where.append(key + "=?")
                    values.append(value)
            condition = " WHERE " + " AND ".join(where) if where else ""
            total = db.execute(
                "SELECT count(*) FROM catalog_override" + condition, values
            ).fetchone()[0]
            rows = db.execute(
                "SELECT * FROM catalog_override"
                + condition
                + " ORDER BY id LIMIT ? OFFSET ?",
                [*values, limit, offset],
            ).fetchall()
            return {
                "items": [resource(row, db, catalogs) for row in rows],
                "total": total,
                "offset": offset,
                "limit": limit,
            }

    def mutate(self, body, key, now, *, override_id=None, expected=None, delete=False):
        with (
            self.store.mutex,
            self.store.acquire() as (catalogs, _private),
            closing(self.store.db()) as db,
            bounded(catalogs, db),
            db,
        ):
            db.execute("BEGIN IMMEDIATE")
            previous = None
            if override_id:
                previous = db.execute(
                    "SELECT * FROM catalog_override WHERE id=?", (override_id,)
                ).fetchone()
                if previous is None:
                    raise ManagementError("not_found", 404, "Resource not found")
                if previous["version"] != expected:
                    raise ManagementError("version_conflict", 412, "Resource changed")
                if delete:
                    db.execute(
                        "DELETE FROM catalog_override WHERE id=?", (override_id,)
                    )
                    current = catalogs.get(previous["provider"])
                    reconcile(
                        db, current[0] if current else None, previous["provider"], now
                    )
                    bump(db)
                    return None
                try:
                    fields(body, set(), {"target", "reason", "enabled"})
                    require(bool(body), "empty patch")
                except ValueError, TypeError:
                    raise ManagementError(
                        "invalid_request", 400, "Invalid override patch"
                    ) from None
                current = json.loads(previous["body"])
                body = {
                    **{
                        k: v
                        for k, v in current.items()
                        if k not in ("fingerprint", "resolution")
                    },
                    **body,
                }
            else:
                try:
                    require(
                        type(key) is str and str(UUID(key)) == key, "idempotency key"
                    )
                except ValueError, TypeError, AttributeError:
                    raise ManagementError(
                        "invalid_request", 400, "UUID Idempotency-Key is required"
                    ) from None
                digest = hashlib.sha256(b"override\0" + dumps(body)).hexdigest()
                db.execute(
                    "DELETE FROM management_idempotency WHERE expires_at<=?", (now,)
                )
                replay = db.execute(
                    "SELECT * FROM management_idempotency WHERE key=?", (key,)
                ).fetchone()
                if replay:
                    if replay["body_digest"] != digest:
                        raise ManagementError(
                            "conflict",
                            409,
                            "Idempotency-Key was used for another request",
                        )
                    saved = json.loads(replay["response"])
                    row = db.execute(
                        "SELECT * FROM catalog_override WHERE id=?", (saved["id"],)
                    ).fetchone()
                    return resource(row, db, catalogs) if row else saved
                if (
                    db.execute(
                        "SELECT count(*) FROM management_idempotency"
                    ).fetchone()[0]
                    >= 10000
                ):
                    raise ManagementError(
                        "queue_full", 503, "Idempotency capacity reached", True
                    )
            validated = self.validate(
                body,
                db,
                catalogs,
                exclude=override_id,
                retained=current if previous else None,
            )
            catalog = catalogs.get(body["provider"])
            validated["resolution"] = list(
                resolution(validated, db, catalog[0] if catalog else None)
            )
            if not writable(
                self.store.private_db,
                self.store.limits["private_metadata_bytes"],
                16384,
            ):
                raise ManagementError(
                    "storage_full", 503, "Private storage capacity reached", True
                )
            if previous:
                db.execute(
                    "UPDATE catalog_override SET namespace=?,body=?,version=version+1,updated_at=? WHERE id=?",
                    (
                        validated["target"]["namespace"],
                        dumps(validated).decode(),
                        now,
                        override_id,
                    ),
                )
            else:
                override_id = str(uuid4())
                db.execute(
                    "INSERT INTO catalog_override VALUES(?,?,?,?,?,?,1,?,?)",
                    (
                        override_id,
                        body["provider"],
                        body["title_id"],
                        body["entity_id"],
                        body["target"]["namespace"],
                        dumps(validated).decode(),
                        now,
                        now,
                    ),
                )
            reconcile(db, catalog[0] if catalog else None, body["provider"], now)
            bump(db)
            row = db.execute(
                "SELECT * FROM catalog_override WHERE id=?", (override_id,)
            ).fetchone()
            result = resource(row, db, catalogs)
            if previous is None:
                db.execute(
                    "INSERT INTO management_idempotency VALUES(?,?,?,?)",
                    (key, digest, dumps(result).decode(), now + 86400),
                )
            return result
