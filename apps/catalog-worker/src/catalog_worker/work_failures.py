"""Current failure classes, without retained exception text or public paths."""

import sqlite3

from catalog_core.diagnostics import REASONS

OUTCOMES = frozenset(
    {
        "http_error",
        "not_found",
        "transport_failure",
        "unexpected_structure",
        "rate_limited",
        "challenge_or_block",
    }
)


def record(
    db: sqlite3.Connection,
    work: dict,
    outcome: str,
    now: int,
    status: int | None,
    parser_reason: str | None,
) -> None:
    db.execute(
        "INSERT INTO work_failure VALUES(?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET "
        "last_failed_at=excluded.last_failed_at,outcome=excluded.outcome,http_status=excluded.http_status,parser_reason=excluded.parser_reason",
        (
            work["path"],
            now,
            # Existing retries predate instrumentation. Their first failure time
            # is unknown; a last successful check is not a failure timestamp.
            now if not work["failures"] else None,
            now,
            outcome if outcome in OUTCOMES else "unknown",
            status if type(status) is int and 100 <= status <= 599 else None,
            parser_reason
            if isinstance(parser_reason, str) and parser_reason in REASONS
            else None,
        ),
    )


def summary(db: sqlite3.Connection, now: int) -> dict:
    """Non-overlapping groups, including uninstrumented pre-upgrade failures."""
    rows = db.execute(
        "SELECT coalesce(f.outcome,'unknown'),f.http_status,f.parser_reason,count(*),"
        "min(f.observed_since),min(f.first_failed_at),min(f.last_failed_at),"
        "sum(f.first_failed_at IS NULL),min(w.failures),max(w.failures),min(w.due),max(w.due),"
        "sum(w.due<=? AND w.lease_until<=?) "
        "FROM work w LEFT JOIN work_failure f USING(path) WHERE w.failures>0 "
        "GROUP BY coalesce(f.outcome,'unknown'),f.http_status,f.parser_reason "
        "ORDER BY 1,2,3",
        (now, now),
    )
    groups = []
    for (
        outcome,
        status,
        reason,
        count,
        since,
        first,
        last,
        unknown,
        low,
        high,
        due,
        latest,
        eligible,
    ) in rows:
        groups.append(
            {
                "outcome": outcome,
                "http_status": status,
                "parser_reason": reason,
                "count": count,
                "observed_since": since,
                "oldest_first_failure_at": first,
                "first_failure_unknown": unknown,
                "oldest_last_failure_at": last,
                "attempts_min": low,
                "attempts_max": high,
                "next_due_min": due,
                "next_due_max": latest,
                "due_now_unleased": eligible,
            }
        )
    return {
        "scope": "current detail-page retries; listing, signals and canonical retries are separate",
        "groups": groups,
    }
