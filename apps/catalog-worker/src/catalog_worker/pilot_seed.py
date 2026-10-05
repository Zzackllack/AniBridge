"""Disposable generated HTML fixture: collector/parser/ledger to read API."""

import argparse
import asyncio
import json
import os
import secrets
import time
from pathlib import Path

from catalog_core.files import ProcessLock, atomic_write
from catalog_core.identity import entity_id, mapping_id, title_id
from catalog_core.json_codec import dumps
from catalog_core.providers.transport import Fetch

from .collector import Collector
from .config import load
from .read_catalog import publish
from .state import State

TITLE = "/anime/stream/generated-client-fixture"
NAME = "Breaking Bad"
TVDB = "81189"


def prepare(config_root: Path) -> Path:
    """No user state, public source, provider request or media is touched."""
    for directory in (config_root, Path("/state"), Path("/read")):
        directory.mkdir(parents=True, exist_ok=True)
        if os.geteuid() == 0:
            os.chown(directory, 1000, 1000)
    worker = config_root / "worker.json"
    if not worker.exists():
        atomic_write(
            worker,
            dumps(
                {
                    "providers": {"aniworld.to": "https://fixture.invalid"},
                    "canonical_sources": {"tv": "off", "movie": "off"},
                    "state_dir": "/state",
                    "output_dir": "/read",
                    "source_id": "private-fixture",
                    "publication_sources": ["synthetic-v1"],
                    "bind_host": "0.0.0.0",
                    "bind_port": 8080,
                }
            ),
        )
        atomic_write(
            config_root / "client.json",
            dumps(
                {
                    "mode": "query",
                    "origin": "http://catalog:8080",
                    "source_id": "private-fixture",
                    "token_file": str(config_root / "metadata-token"),
                    "allow_private_http": True,
                }
            ),
        )
        atomic_write(config_root / "metadata-token", secrets.token_urlsafe(32).encode())
        (config_root / "metadata-token").chmod(0o600)
        for path in config_root.iterdir():
            if os.geteuid() == 0:
                os.chown(path, 1000, 1000)
    return worker


async def seed(config_path: Path) -> dict:
    config = load(config_path)
    state = State(config.state_dir / "aniworld.to.sqlite", "aniworld.to")
    try:
        if state.db.execute("SELECT count(*) FROM title").fetchone()[0]:
            return {"already_seeded": True}
        now = int(time.time())
        episodes = [TITLE + f"/staffel-1/episode-{n}" for n in range(1, 21)]
        pages = {
            "/animes-alphabet": f'<html><body><a href="{TITLE}">{NAME}</a></body></html>',
            TITLE: "<html><body><h1>"
            + NAME
            + "</h1>"
            + "".join(f'<a href="{path}">Episode</a>' for path in episodes)
            + "</body></html>",
        }
        pages.update(
            {
                path: '<html><body><h1>Generated</h1><li data-lang-key="1" data-link-target="/redirect/fixture"></li><li data-lang-key="2" data-link-target="/redirect/fixture"></li></body></html>'
                for path in episodes
            }
        )
        requests = 0

        async def fetch(origin, path, **options):
            nonlocal requests
            requests += 1
            if requests > 24:
                raise ValueError("fixture request bound")
            return Fetch("ok", pages[path].encode())

        collector = Collector(config, state, fetcher=fetch)
        async with asyncio.timeout(60):
            for _ in range(24):
                plan = collector.prepare(signal_allowed=False)
                if plan is None:
                    break
                collector.apply(await collector.collect(plan))
        tid = title_id("aniworld.to", TITLE)
        mid = mapping_id("aniworld.to", tid, "tvdb", TVDB)
        with state.db:
            state.db.execute(
                "INSERT INTO canonical_title VALUES(?,?,?,?,?,?,?)",
                (mid, tid, "tvdb", TVDB, "synthetic-v1", "reviewed", now),
            )
            for n, path in enumerate(episodes, 1):
                state.db.execute(
                    "INSERT INTO canonical_episode VALUES(?,?,?,?,?,?,?)",
                    (mid, entity_id("aniworld.to", path), 1, n, None, "reviewed", now),
                )
        metadata = publish(config, state, int(time.time()))
        return {
            "generated_title": NAME,
            "episodes": 20,
            "releases": metadata["counts"]["release"],
            "fixture_fetches": requests,
        }
    finally:
        state.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare isolated generated query pilot"
    )
    parser.add_argument("config_root", type=Path)
    args = parser.parse_args()
    config_path = prepare(args.config_root)
    if os.geteuid() == 0:
        os.setgid(1000)
        os.setuid(1000)
    lock = ProcessLock(Path("/state") / "worker.lock")
    try:
        print(json.dumps(asyncio.run(seed(config_path))))
    finally:
        lock.close()


if __name__ == "__main__":
    main()
