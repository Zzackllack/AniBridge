"""Explicit collector and read-serving commands; no hosted default."""

import argparse
import asyncio
import signal
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

from catalog_core.files import ProcessLock
from catalog_core.supervisor import run_child_async

from .canonical import Enricher
from .collector import Collector
from .config import load
from .events import Events
from .pipeline import Pipeline
from .state import State
from .storage import check, migration_reserve, recover_scratch


async def collect(path: Path, once: bool) -> None:
    if sys.platform != "linux":
        raise ValueError("collector resource enforcement requires Linux")
    config = load(path)
    if set(config.providers) != {"aniworld.to"}:
        raise ValueError("query pilot currently serves AniWorld only")
    config.output_dir.mkdir(parents=True, exist_ok=True)
    owner = ProcessLock(config.state_dir / "worker.lock")
    state = None
    events = Events(config.state_dir / "logs")
    tasks = []
    try:
        recover_scratch(config.state_dir)
        check(config, startup=True, state_reserve=migration_reserve(config))
        state = State(config.state_dir / "aniworld.to.sqlite", "aniworld.to")
        pipeline = Pipeline([Collector(config, state)], events.emit)
        enricher = Enricher(config.canonical_sources)
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, asyncio.current_task().cancel)

        async def maintain() -> None:
            while True:
                try:
                    check(config)
                    await enricher.tick(state, int(time.time()))
                    meta = state.meta()
                    if (
                        meta["listing_checked_at"]
                        and (
                            meta["dirty"]
                            or not (config.output_dir / "current.json").exists()
                        )
                        and time.time() - meta["published_at"]
                        >= config.limits["publish_interval_s"]
                    ):
                        async with pipeline.publication(state.provider):
                            await run_child_async(
                                "catalog_worker.query_publish", [str(path)], 420
                            )
                except (ValueError, OSError, sqlite3.Error) as exc:
                    events.emit(state.provider, "maintain", type(exc).__name__, 0)
                if once:
                    return
                await asyncio.sleep(1)

        if once:
            await pipeline.run(once=True)
            await maintain()
        else:
            tasks = [
                asyncio.create_task(pipeline.run()),
                asyncio.create_task(maintain()),
            ]
            await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if state is not None:
            state.close()
        events.close()
        owner.close()


async def collect_title(path: Path, title_path: str) -> None:
    """One deliberately selected title, at most 30 metadata requests/120 seconds."""
    from catalog_core.identity import path as validate_path
    from catalog_core.providers.aniworld import TITLE, Link, Page

    from .read_catalog import publish

    config = load(path)
    if sys.platform != "linux" or not TITLE.fullmatch(validate_path(title_path)):
        raise ValueError("Linux and a valid AniWorld title path required")
    config.state_dir.mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    owner = ProcessLock(config.state_dir / "worker.lock")
    state = None
    try:
        check(config, startup=True, state_reserve=migration_reserve(config))
        state = State(config.state_dir / "aniworld.to.sqlite", "aniworld.to")
        existing = state.db.execute("SELECT path,display_title FROM title").fetchall()
        if existing and [row["path"] for row in existing] != [title_path]:
            raise ValueError(
                "targeted command requires empty or matching single-title state"
            )
        now = int(time.time())
        # This is a synthetic discovery hint, not a fresh provider listing.
        # Resuming must keep the heading already obtained from the detail page.
        name = (
            existing[0]["display_title"] if existing else title_path.rsplit("/", 1)[-1]
        )
        state.listing(Page((Link(title_path, name),), (), 0, None), now)
        collector = Collector(config, state)
        async with asyncio.timeout(120):
            for _ in range(30):
                plan = collector.prepare(listing_allowed=False, signal_allowed=False)
                if plan is None:
                    break
                ready = await collector.collect(plan)
                collector.apply(ready)
                if ready.outcome != "ok":
                    raise ValueError(
                        "selected title metadata unavailable: " + ready.outcome
                    )
            await Enricher(config.canonical_sources).tick(state, int(time.time()))
        publish(config, state, int(time.time()))
    finally:
        if state is not None:
            state.close()
        owner.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AniBridge private metadata collector/API"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--collect-title", metavar="NATIVE_PATH")
    parser.add_argument("--review-season", type=Path)
    args = parser.parse_args()
    config = load(args.config)
    if args.serve:
        import uvicorn

        from .query_server import create_app
        from .read_catalog import verify

        if args.token_file is None:
            parser.error("--serve requires --token-file")
        verify(config.output_dir)
        uvicorn.run(
            create_app(config.output_dir, args.token_file.read_text().strip()),
            host=config.bind_host,
            port=config.bind_port,
            access_log=False,
            log_level="warning",
            workers=1,
            limit_concurrency=32,
            timeout_keep_alive=5,
            proxy_headers=False,
        )
    elif args.collect_title:
        asyncio.run(collect_title(args.config, args.collect_title))
    elif args.review_season:
        from catalog_core.json_codec import loads

        from .review import season

        with closing(ProcessLock(config.state_dir / "worker.lock")):
            state = State(config.state_dir / "aniworld.to.sqlite", "aniworld.to")
            try:
                season(state, loads(args.review_season.read_bytes(), 16384))
            finally:
                state.close()
    elif args.publish:
        from .query_publish import publish_config

        with closing(ProcessLock(config.state_dir / "worker.lock")):
            publish_config(args.config)
    else:
        try:
            asyncio.run(collect(args.config, args.once))
        except (KeyboardInterrupt, asyncio.CancelledError):
            pass


if __name__ == "__main__":
    main()
