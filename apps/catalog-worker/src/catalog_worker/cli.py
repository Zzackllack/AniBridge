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
from catalog_core.supervisor import ChildDeadline, ChildFailure, run_child_async

from .canonical import Enricher
from .collector import Collector
from .config import load
from .events import Events
from .pipeline import Pipeline
from .read_catalog import provider_root
from .state import State
from .storage import check, migration_reserve, recover_scratch


async def collect(path: Path, once: bool) -> None:
    if sys.platform != "linux":
        raise ValueError("collector resource enforcement requires Linux")
    config = load(path)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    owner = ProcessLock(config.state_dir / "worker.lock")
    states = []
    events = Events(config.state_dir / "logs")
    tasks = []
    collectors = []
    enricher = None
    try:
        recover_scratch(config.state_dir)
        check(config, startup=True, state_reserve=migration_reserve(config))
        states = [
            State(config.state_dir / f"{provider}.sqlite", provider)
            for provider in config.providers
        ]
        collectors = [Collector(config, state) for state in states]
        pipeline = Pipeline(collectors, events.emit)
        publication_slot = asyncio.Lock()
        enricher = Enricher(config.canonical_sources, states=states)
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, asyncio.current_task().cancel)

        async def maintain(state: State) -> None:
            while True:
                try:
                    check(config)
                    started = time.monotonic()
                    try:
                        await enricher.tick(state, int(time.time()))
                    except (ValueError, OSError, sqlite3.Error) as exc:
                        events.emit(
                            state.provider,
                            "enrichment",
                            type(exc).__name__,
                            time.monotonic() - started,
                        )
                        raise
                    events.emit(
                        state.provider,
                        "enrichment",
                        enricher.last_work,
                        time.monotonic() - started,
                    )
                    meta = state.meta()
                    if (
                        state.db.execute("SELECT 1 FROM release LIMIT 1").fetchone()
                        and (
                            meta["dirty"]
                            or not (
                                provider_root(config.output_dir, state.provider)
                                / "current.json"
                            ).exists()
                        )
                        and time.time() - meta["published_at"]
                        >= config.limits["publish_interval_s"]
                    ):
                        async with (
                            publication_slot,
                            pipeline.publication(state.provider),
                        ):
                            records = await run_child_async(
                                "catalog_worker.query_publish",
                                [str(path), state.provider],
                                420,
                            )
                            events.child(state.provider, records, exit_code=0)
                except (ChildFailure, ChildDeadline) as exc:
                    events.child(state.provider, exc.records, exc.exit_code, exc.reason)
                except (ValueError, OSError, sqlite3.Error) as exc:
                    events.emit(state.provider, "maintain", type(exc).__name__, 0)
                if once:
                    return
                await asyncio.sleep(1)

        if once:
            await pipeline.run(once=True)
            await asyncio.gather(*(maintain(state) for state in states))
        else:
            tasks = [
                asyncio.create_task(pipeline.run()),
                *(asyncio.create_task(maintain(state)) for state in states),
            ]
            await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if enricher is not None:
            await enricher.close()
        for collector in collectors:
            await collector.close()
        for state in states:
            state.close()
        events.close()
        owner.close()


async def collect_title(
    path: Path, title_path: str, provider: str = "aniworld.to"
) -> None:
    """One deliberately selected title, at most 30 metadata requests/120 seconds."""
    from catalog_core.identity import path as validate_path
    from catalog_core.providers.adapters import adapter
    from catalog_core.providers.aniworld import Link

    from .read_catalog import publish

    config = load(path)
    if (
        sys.platform != "linux"
        or provider not in config.providers
        or not adapter(provider).TITLE.fullmatch(validate_path(title_path))
    ):
        raise ValueError("Linux and an enabled provider title path required")
    config.state_dir.mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    owner = ProcessLock(config.state_dir / "worker.lock")
    state = None
    collector = None
    try:
        check(config, startup=True, state_reserve=migration_reserve(config))
        state = State(config.state_dir / f"{provider}.sqlite", provider)
        existing = state.db.execute(
            "SELECT path,display_title FROM title WHERE path=?", (title_path,)
        ).fetchall()
        now = int(time.time())
        # This is a synthetic discovery hint, not a fresh provider listing.
        # Resuming must keep the heading already obtained from the detail page.
        name = (
            existing[0]["display_title"] if existing else title_path.rsplit("/", 1)[-1]
        )
        tid = state.discover(Link(title_path, name), now)
        state.db.commit()
        collector = Collector(config, state)
        enricher = Enricher(config.canonical_sources)
        async with asyncio.timeout(120):
            for _ in range(30):
                work = state.claim_title(
                    tid, int(time.time()), config.limits["title_deadline_s"]
                )
                if work is None:
                    break
                from .collector import Plan

                plan = Plan(int(time.time()), False, work, work["path"])
                if plan is None:
                    break
                ready = await collector.collect(plan)
                collector.apply(ready)
                if ready.outcome == "admission_deferred":
                    await asyncio.sleep(ready.retry_after)
                    continue
                if ready.outcome != "ok":
                    raise ValueError(
                        "selected title metadata unavailable: " + ready.outcome
                    )
            await enricher.tick(state, int(time.time()), title_id=tid)
        publish(config, state, int(time.time()))
    finally:
        if collector is not None:
            await enricher.close()
            await collector.close()
        if state is not None:
            state.close()
        owner.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="AniBridge private metadata collector/API"
    )
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--provider", choices=("aniworld.to", "s.to", "megakino"), default="aniworld.to"
    )
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--backup", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--collect-title", metavar="NATIVE_PATH")
    parser.add_argument("--review-season", type=Path)
    args = parser.parse_args()
    config = load(args.config)
    if args.status:
        import json

        from .operator_status import report

        print(json.dumps(report(config), indent=2))
    elif args.backup:
        from .backup import backup

        with closing(ProcessLock(config.state_dir / "worker.lock")):
            print(backup(config))
    elif args.serve:
        import uvicorn

        from .query_server import create_app
        from .read_catalog import verify

        if args.token_file is None:
            parser.error("--serve requires --token-file")
        for provider in config.providers:
            root = provider_root(config.output_dir, provider)
            if (root / "current.json").exists():
                verify(root)
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
        asyncio.run(collect_title(args.config, args.collect_title, args.provider))
    elif args.review_season:
        from catalog_core.json_codec import loads

        from .review import season

        with closing(ProcessLock(config.state_dir / "worker.lock")):
            state = State(config.state_dir / f"{args.provider}.sqlite", args.provider)
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
        except KeyboardInterrupt, asyncio.CancelledError:
            pass


if __name__ == "__main__":
    main()
