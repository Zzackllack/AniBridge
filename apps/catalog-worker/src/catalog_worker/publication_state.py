"""Publication admission and acknowledgements use captured generations."""

import sqlite3

from catalog_core.json_codec import loads

from .config import Config
from .publication_base import policy
from .state import State


def pending(config: Config, state: State, now: int) -> bool:
    """Content uses the normal cadence; routine observations have their own clock."""
    row = state.db.execute("SELECT * FROM publication_meta").fetchone()
    age = now - state.meta()["published_at"]
    interval = config.limits["publish_interval_s"]
    freshness_interval = config.limits["publish_freshness_interval_s"]
    try:
        prior = loads(row["receipt"].encode()) if row["receipt"] else {}
        stale_policy = any(prior.get(k) != v for k, v in policy(config).items())
    except (ValueError, AttributeError):
        stale_policy = True
    if stale_policy:
        return age >= interval
    return row["generation"] > row["published_generation"] and age >= (
        interval
        if row["content_generation"] > row["published_content_generation"]
        else max(interval, freshness_interval)
    )


def acknowledge(
    db: sqlite3.Connection, generation: int, content: int, receipt: str, now: int
) -> None:
    """Newer observations must survive a publication completing behind them."""
    with db:
        db.execute(
            "UPDATE publication_meta SET published_generation=?,published_content_generation=?,receipt=?",
            (generation, content, receipt),
        )
        db.execute("DELETE FROM publication_change WHERE generation<=?", (generation,))
        db.execute(
            "UPDATE worker_meta SET dirty=(SELECT generation>published_generation FROM publication_meta),published_at=?",
            (now,),
        )
