"""Own the finite metadata cache and user-local durable job scheduler."""

import asyncio
import sys
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

from catalog_core.files import ProcessLock
from catalog_core.query_client import Cache, Client

from .client import ClientJobs
from .config import Config
from .executor import SubprocessExecutor
from .jobs import Jobs
from .query_local import Search
from .runner import Runner
from .strm_http import Playback
from .async_database import call


class Runtime:
    def __init__(
        self,
        config: Config,
        database: Path,
        directory: Path,
        downloads: Path,
        origins: dict[str, str],
        hosts: tuple[str, ...],
        *,
        executor=None,
        transport=None,
        clock=time.time,
        strm_mode="direct",
    ) -> None:
        if config.mode != "query" or set(origins) != {"aniworld.to"}:
            raise ValueError("query pilot requires only AniWorld enabled")
        if executor is None and sys.platform != "linux":
            raise ValueError("private job enforcement requires Linux; use Docker")
        directory.mkdir(parents=True, exist_ok=True)
        self.owner = ProcessLock(directory / "query.lock")
        self.directory = directory
        self.tasks = []
        self.clock = clock
        self.config = config
        try:
            self.metadata = None
            self.search = None
            try:
                self.metadata = Client(
                    config.origin,
                    config.source_id,
                    config.token_file.read_text().strip(),
                    Cache(directory / "query-cache.sqlite"),
                    transport=transport,
                    allow_private_http=config.allow_private_http,
                )
                self.search = Search(self.metadata, database, directory)
            except sqlite3.Error:
                # A broken disposable cache cannot stop already accepted local jobs.
                # Search fails explicitly until the operator repairs that cache.
                pass
            self.jobs = Jobs(
                database,
                downloads,
                set(origins),
                metadata_limit=1024**3,
                hosts=hosts,
                strm_mode=strm_mode,
            )
            self.client = ClientJobs(self.jobs)
            self.runner = Runner(
                self.jobs,
                executor
                or SubprocessExecutor(origins, hosts, downloads, strm_mode=strm_mode),
                clock=clock,
                concurrency=1,
            )
            # Playback only needs a scratch directory, never a snapshot registry.
            self.playback = Playback(
                SimpleNamespace(directory=directory), self.jobs, origins, hosts
            )
        except BaseException:
            self.owner.close()
            raise

    def mapping_check(self, payload: dict) -> str | None:
        # The accepted self-contained request remains usable after cache eviction
        # or service loss. Identity/path checks happen in Jobs.decode/admission.
        if not payload.get("legacy"):
            payload["catalog_source"] = {
                "source_id": self.config.source_id,
                "origin": self.config.origin,
            }
            return "local_request"
        return None

    def legacy_path(self, payload: dict) -> None:
        return None

    async def removals(self) -> None:
        while True:
            try:
                await call(
                    self.client.settle_removals,
                    set(self.runner.running),
                    int(self.clock()),
                )
            except (OSError, sqlite3.Error):
                await asyncio.sleep(1)
            await asyncio.sleep(0.1)

    @asynccontextmanager
    async def running(self):
        try:
            self.tasks = [
                asyncio.create_task(self.runner.run()),
                asyncio.create_task(self.removals()),
            ]
            yield self
        finally:
            for task in self.tasks:
                task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)
            try:
                await self.playback.close()
                if self.metadata is not None:
                    await self.metadata.close()
            finally:
                self.owner.close()
