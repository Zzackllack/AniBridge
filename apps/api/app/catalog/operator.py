"""Apply reviewed local corrections from a JSON file; never publish them."""

import argparse
import asyncio
import sqlite3
import tempfile
import threading
import time
from contextlib import closing, contextmanager
from pathlib import Path
from uuid import uuid4

from catalog_core.protocol import Request
from catalog_core.query_client import Cache, Client
from catalog_core.json_codec import loads, require
from catalog_core import schema

from .config import load
from .overrides import Overrides
from .query_local import materialize


class CorrectionStore:
    """Request-owned read fixture for the existing correction validation service."""

    def __init__(self, database: Path, read: Path, metadata: dict) -> None:
        self.private_db, self.read, self.metadata = database, read, metadata
        self.providers = ("aniworld.to",)
        self.limits = {"private_metadata_bytes": 1024**3}
        self.mutex = threading.Lock()

    def db(self):
        db = sqlite3.connect(self.private_db, timeout=0.2)
        db.row_factory = sqlite3.Row
        return db

    @contextmanager
    def acquire(self):
        with closing(schema.connect(self.read)) as read, closing(self.db()) as private:
            yield {"aniworld.to": (read, self.metadata)}, private


async def apply(config_file: str, database: Path, directory: Path, body: dict) -> dict:
    config = load(config_file)
    require(config.mode == "query", "query configuration required")
    client = Client(
        config.origin,
        config.source_id,
        config.token_file.read_text().strip(),
        Cache(directory / "query-cache.sqlite"),
        allow_private_http=config.allow_private_http,
    )
    try:
        key = {"tvdb": "tvdbid", "tmdb-tv": "tmdbid", "imdb": "imdbid"}[
            body["target"]["namespace"]
        ]
        candidates = await client.fetch(
            Request(
                operation="titles",
                params={"t": "tvsearch", key: body["target"]["external_id"]},
            )
        )
        titles = {title.title_id for title in candidates.response.titles} | {
            body["title_id"]
        }
        batches = []
        for offset in range(0, 2000, 500):
            result = await client.fetch(
                Request(
                    operation="native",
                    params={"t": "search"},
                    title_ids=sorted(titles),
                    offset=offset,
                )
            )
            require(
                result.state != "stale",
                "current metadata required to create a correction",
            )
            require(result.response.total <= 2000, "query_too_broad")
            batches.append(result.response)
            if offset + len(result.response.rows) >= result.response.total:
                break
        require(
            len({(r.revision, r.snapshot_digest) for r in batches}) == 1,
            "catalog changed; retry correction",
        )
        with tempfile.TemporaryDirectory(
            prefix="override-", dir=directory
        ) as temporary:
            read = Path(temporary) / "rows.sqlite"
            metadata = materialize(read, batches)
            store = CorrectionStore(database, read, metadata)
            return Overrides(store).mutate(body, str(uuid4()), int(time.time()))
    finally:
        await client.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply a reviewed AniWorld local correction"
    )
    parser.add_argument("body", type=Path)
    args = parser.parse_args()
    from app.config import DATA_DIR
    import os

    result = asyncio.run(
        apply(
            os.environ["CATALOG_CONFIG_FILE"],
            DATA_DIR / "anibridge_jobs.db",
            DATA_DIR / "catalog",
            loads(args.body.read_bytes(), 16384),
        )
    )
    print("Created local correction " + result["id"])


if __name__ == "__main__":
    main()
