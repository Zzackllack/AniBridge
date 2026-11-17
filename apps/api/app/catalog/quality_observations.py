"""Compact actual-download evidence committed alongside durable completion."""

from catalog_core.json_codec import dumps

from .quality_evidence import valid_record


def retain(db, key: str, payload: dict, evidence: dict | None, now: int) -> None:
    if payload.get("legacy") or not evidence:
        return
    row = {
        name: payload.get(name)
        for name in (
            "provider",
            "title_id",
            "entity_id",
            "path",
            "native_season",
            "language",
            "host_preference",
        )
    }
    # Validate before storing data from an executor, including injected executors.
    if not valid_record(
        {
            **evidence,
            "outcome": "ok",
            "entity_id": row["entity_id"],
            "path": row["path"],
            "scope": "pending",
            "snapshot": "pending",
            "measured_at": now,
        }
    ):
        return
    body = dumps({"row": row, "evidence": evidence, "measured_at": now}).decode()
    if len(body.encode()) > 4096:
        return
    db.execute(
        "DELETE FROM catalog_cache WHERE kind='sample-observation' AND expires_at<=?",
        (now,),
    )
    db.execute(
        "INSERT OR REPLACE INTO catalog_cache VALUES('sample-observation',?,?,?,?)",
        (key, body, now + 604800, now),
    )
    db.execute(
        "DELETE FROM catalog_cache WHERE kind='sample-observation' AND key IN "
        "(SELECT key FROM catalog_cache WHERE kind='sample-observation' ORDER BY used_at DESC,key DESC LIMIT -1 OFFSET 32)"
    )
