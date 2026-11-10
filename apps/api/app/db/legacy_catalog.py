"""Preserve interrupted mainline requests without inventing missing inputs."""

import json

from sqlalchemy.engine import Connection

INTERRUPTED = (
    "queued",
    "resolving",
    "downloading",
    "retry_wait",
    "paused",
    "blocked",
    "cancelling",
)


def preserve_incomplete_requests(connection: Connection) -> None:
    # Released Job/ClientTask records did not persist mode or host preference.
    # A filename/display label cannot supply either. Retain every original
    # private row and expose why these jobs cannot safely resume.
    after = ""
    while True:
        rows = connection.exec_driver_sql(
            "SELECT id,status,source_site FROM job WHERE id>? AND status IN ("
            + ",".join("?" for _ in INTERRUPTED)
            + ") ORDER BY id LIMIT 100",
            (after, *INTERRUPTED),
        ).fetchall()
        if not rows:
            return
        after = rows[-1][0]
        # Do not mutate an open cursor over the same selection: SQLite makes
        # visibility of those changes undefined. Bound and settle each page.
        for job_id, state, provider in rows:
            payload = json.dumps(
                {
                    "legacy": True,
                    "provider": provider,
                    "mode": None,
                    "release_id": None,
                    "entity_id": None,
                    "canonical": None,
                    "incomplete": True,
                },
                separators=(",", ":"),
            )
            connection.exec_driver_sql(
                "INSERT INTO durable_request(job_id,payload,prior_state,error_code) VALUES(?,?,?,'legacy_request_incomplete')",
                (job_id, payload, state),
            )
            connection.exec_driver_sql(
                "UPDATE job SET status='failed',speed=0,message='legacy_request_incomplete: original mode and host preference were not persisted; request cannot safely resume' WHERE id=?",
                (job_id,),
            )
