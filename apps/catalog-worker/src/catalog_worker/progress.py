"""Coverage phases and qualified rates; growing discovery queues have no finish ETA."""

from .work_failures import summary as failure_summary


def canonical_queue(db, now: int) -> dict:
    """Expose retry starvation separately from provider page failures.

    These are persisted deadlines; admission and matcher invalidation can affect
    execution. A zero deadline means new evidence, not an epoch-old backlog.
    """
    first, due, failed, cached, oldest, oldest_failed = db.execute(
        "SELECT count(CASE WHEN checked_at IS NULL THEN 1 END),"
        "count(CASE WHEN next_due<=? THEN 1 END),"
        "count(CASE WHEN failures>0 AND next_due<=? THEN 1 END),"
        "count(CASE WHEN failures>0 AND next_due<=? AND EXISTS("
        "SELECT 1 FROM canonical_cache c WHERE c.title_id=m.title_id) THEN 1 END),"
        "min(CASE WHEN next_due>0 AND next_due<=? THEN next_due END),"
        "min(CASE WHEN failures>0 AND next_due>0 AND next_due<=? THEN next_due END) "
        "FROM mapping_input m",
        (now, now, now, now, now),
    ).fetchone()
    return {
        "never_checked": first,
        "due_now": due,
        "failed_due_now": failed,
        "cached_failed_due_now": cached,
        "oldest_due_age_s": now - oldest if oldest is not None else None,
        "oldest_failed_due_age_s": now - oldest_failed
        if oldest_failed is not None
        else None,
    }


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
    unavailable = db.execute(
        "SELECT count(*) FROM work WHERE fingerprint LIKE 'unavailable:%'"
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
    due, deferred, leased, next_due, retry_due = db.execute(
        "SELECT coalesce(sum(checked_at IS NULL AND due<=? AND lease_until<=?),0),"
        "coalesce(sum(checked_at IS NULL AND due>?),0),"
        "coalesce(sum(checked_at IS NULL AND lease_until>?),0),"
        "min(CASE WHEN checked_at IS NULL AND due>? THEN due END),"
        "coalesce(sum(failures>0 AND due<=? AND lease_until<=?),0) FROM work",
        (now, now, now, now, now, now, now),
    ).fetchone()
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
        # These are scheduled deadlines, not a claim that provider budgets or
        # circuits permit a request. Idle bootstrap may admit deferred new work.
        "queue": {
            "pending_due_now": due,
            "pending_deferred": deferred,
            "pending_leased": leased,
            "next_pending_due": next_due,
            "failed_due_now": retry_due,
        },
        "canonical_queue": canonical_queue(db, now),
        "page_failures": failure_summary(db, now) if "work_failure" in tables else None,
        "first_pass_complete": first_pass,
        "detail_evidence_complete": first_pass and unknown == 0 and unavailable == 0,
        "unavailable_episode_observations": unavailable,
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
