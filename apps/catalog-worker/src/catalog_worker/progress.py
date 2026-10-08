"""Coverage phases and qualified rates; growing discovery queues have no finish ETA."""


def measure(db, meta: dict, now: int) -> dict:
    by_kind = {
        row[0]: {"discovered": row[1], "checked": row[2], "failed": row[3]}
        for row in db.execute(
            "SELECT kind,count(*),count(checked_at),sum(failures>0) FROM work GROUP BY kind"
        )
    }
    unknown = db.execute(
        "SELECT coalesce(sum(unknown_languages),0) FROM observation_gap"
    ).fetchone()[0]
    usable, mapped = db.execute(
        "SELECT count(*),coalesce(sum(EXISTS(SELECT 1 FROM canonical_episode c WHERE c.entity_id=e.entity_id)),0) "
        "FROM entity e WHERE kind='episode' AND EXISTS(SELECT 1 FROM release r WHERE r.entity_id=e.entity_id)"
    ).fetchone()
    last_hour = db.execute(
        "SELECT count(*) FROM work WHERE checked_at>?", (now - 3600,)
    ).fetchone()[0]
    requests = db.execute(
        "SELECT count(*) FROM request_start WHERE at>?", (now - 3600,)
    ).fetchone()[0]
    pending = sum(v["discovered"] - v["checked"] for v in by_kind.values())
    failures = sum(v["failed"] for v in by_kind.values())
    discovery_open = not meta["listing_checked_at"] or any(
        v["discovered"] != v["checked"]
        for kind, v in by_kind.items()
        if kind != "episode"
    )
    tables = {
        r[0] for r in db.execute("SELECT name FROM sqlite_schema WHERE type='table'")
    }
    stats = (
        dict(db.execute("SELECT * FROM collection_stats").fetchone())
        if "collection_stats" in tables
        else {}
    )
    unsupported = db.execute(
        "SELECT count(*) FROM title WHERE media_type='unknown'"
    ).fetchone()[0]
    first_pass = bool(
        meta["listing_checked_at"] and not pending and not failures and not unsupported
    )
    return {
        "phases": by_kind,
        "first_pass_complete": first_pass,
        "detail_evidence_complete": first_pass and unknown == 0,
        "unknown_language_observations": unknown,
        "episodes_with_releases": usable,
        "mapped_with_releases": mapped,
        "mapping_fraction": mapped / usable if usable else None,
        "checked_pages_last_hour": last_hour,
        "requests_last_hour": requests,
        "stats": stats,
        "eta_seconds": None
        if discovery_open or not last_hour
        else round(pending * 3600 / last_hour),
        "eta_scope": "current discovered queue only; retries, future changes and canonical enrichment excluded",
        "discovery_queue_can_grow": discovery_open,
    }
