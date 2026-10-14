"""Apply positive season evidence without treating omitted flags as deletion."""

import hashlib

from catalog_core.json_codec import dumps

from .aniworld import Page


def admit(
    state, parent: dict, page: Page, now: int, interval: int, history: int
) -> None:
    for row in page.episodes:
        if not row.path.startswith(parent["path"] + "/"):
            continue
        work = state.db.execute(
            "SELECT * FROM work WHERE path=? AND kind='episode'", (row.path,)
        ).fetchone()
        if work is None or work["lease_until"] > now:
            continue
        fingerprint = hashlib.sha256(
            dumps([row.title, row.aliases, row.languages, row.unknown_languages])
        ).hexdigest()
        previous = state.db.execute(
            "SELECT fingerprint FROM batch_observation WHERE path=?", (row.path,)
        ).fetchone()
        changed = previous is not None and previous[0] != fingerprint
        complete = bool(row.title and row.languages and not row.unknown_languages)
        # Even incomplete rows add trustworthy names/flags, but leave detail due.
        if row.title or row.languages:
            state.detail(
                {**dict(work), "batch": True},
                Page(
                    (),
                    tuple(row.languages),
                    row.unknown_languages,
                    None,
                    episode_title=row.title,
                    episode_aliases=tuple(row.aliases),
                    availability="unavailable"
                    if not row.languages
                    and (work["fingerprint"] or "").startswith("unavailable:")
                    else "available",
                ),
                now,
                interval,
                history,
            )
        state.db.execute(
            "INSERT INTO batch_observation VALUES(?,?) ON CONFLICT(path) DO UPDATE SET fingerprint=excluded.fingerprint",
            (row.path, fingerprint),
        )
        if not complete or changed or work["failures"]:
            state.db.execute(
                "UPDATE work SET checked_at=?,failures=?,due=? WHERE path=?",
                (
                    work["checked_at"],
                    work["failures"],
                    max(now, work["due"]) if work["failures"] else now,
                    row.path,
                ),
            )
        else:
            # Season reconciliation refreshes the row. Detail reconciliation is
            # retained as a bounded fallback, not every episode on bootstrap.
            state.db.execute(
                "UPDATE work SET due=? WHERE path=?", (now + history, row.path)
            )
