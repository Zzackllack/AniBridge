"""
Migration: add source_site columns for dual catalogue support.

Usage:
    python scripts/migrations/20251018_add_source_site.py
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlmodel import create_engine

from app.config import DATA_DIR
from app.db.models import Job, EpisodeAvailability


def _column_exists(conn: Connection, table: str, column: str) -> bool:
    result = conn.execute(text(f"PRAGMA table_info('{table}')"))
    return any(row[1] == column for row in result)


def _ensure_job_source_site(conn: Connection) -> None:
    table = Job.__table__.name
    if _column_exists(conn, table, "source_site"):
        return
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN source_site TEXT"))
    conn.execute(
        text(f"UPDATE {table} SET source_site = 'aniworld' WHERE source_site IS NULL")
    )


def _rebuild_episodeavailability(conn: Connection) -> None:
    old_table = EpisodeAvailability.__table__.name
    if _column_exists(conn, old_table, "source_site"):
        return

    new_table = f"{old_table}_new"
    conn.execute(
        text(
            f"""
            CREATE TABLE {new_table} (
                source_site TEXT NOT NULL DEFAULT 'aniworld',
                slug TEXT NOT NULL,
                season INTEGER NOT NULL,
                episode INTEGER NOT NULL,
                language TEXT NOT NULL,
                available INTEGER,
                height INTEGER,
                vcodec TEXT,
                provider TEXT,
                checked_at TEXT NOT NULL,
                extra JSON,
                PRIMARY KEY (source_site, slug, season, episode, language)
            )
            """
        )
    )

    conn.execute(
        text(
            f"""
            INSERT INTO {new_table} (
                source_site,
                slug,
                season,
                episode,
                language,
                available,
                height,
                vcodec,
                provider,
                checked_at,
                extra
            )
            SELECT
                'aniworld',
                slug,
                season,
                episode,
                language,
                available,
                height,
                vcodec,
                provider,
                checked_at,
                extra
            FROM {old_table}
            """
        )
    )

    conn.execute(text(f"DROP TABLE {old_table}"))
    conn.execute(text(f"ALTER TABLE {new_table} RENAME TO {old_table}"))
    conn.execute(
        text(
            f"CREATE INDEX IF NOT EXISTS ix_{old_table}_checked_at "
            f"ON {old_table} (checked_at)"
        )
    )


def main() -> None:
    db_path = DATA_DIR / "anibridge_jobs.db"
    if not db_path.exists():
        raise SystemExit(f"Database not found at {db_path}. Run bootstrap first.")

    engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"timeout": 30})
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=OFF"))
        _ensure_job_source_site(conn)
        _rebuild_episodeavailability(conn)
        conn.execute(text("PRAGMA foreign_keys=ON"))


if __name__ == "__main__":
    main()
