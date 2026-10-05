"""Finite user-local request cache; outage coverage is limited to prior pages."""

import asyncio
import hashlib
import sqlite3
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from catalog_core.json_codec import dumps, loads

from .protocol import MAX_RESPONSE, Request, Response


class Unavailable(Exception):
    """An uncached request failed; never translate this to an empty result."""


@dataclass(frozen=True)
class Result:
    response: Response
    state: str
    age_s: float
    error: str | None = None


class Cache:
    def __init__(
        self, filename: Path, *, entries: int = 128, payload_bytes: int = 2 * 1024**2
    ) -> None:
        if not 1 <= entries <= 128 or not 1 <= payload_bytes <= 2 * 1024**2:
            raise ValueError("cache limits outside pilot bounds")
        self.filename, self.entries, self.payload_bytes = (
            filename,
            entries,
            payload_bytes,
        )
        with closing(self.connect()) as db, db:
            db.execute("PRAGMA journal_mode=DELETE")
            db.execute(
                "CREATE TABLE IF NOT EXISTS entry(key TEXT PRIMARY KEY,body BLOB NOT NULL,fetched REAL NOT NULL,used REAL NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS revision_floor(scope TEXT PRIMARY KEY,revision INTEGER NOT NULL)"
            )
        filename.chmod(0o600)

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.filename, timeout=0.2)
        if db.execute("PRAGMA page_size").fetchone()[0] != 4096:
            db.close()
            raise ValueError("cache requires 4-KiB pages")
        db.execute("PRAGMA max_page_count=4096")  # 16 MiB at default 4-KiB pages.
        return db

    def get(self, key: str, now: float) -> tuple[bytes, float] | None:
        db = self.connect()
        try:
            with db:
                row = db.execute(
                    "SELECT body,fetched FROM entry WHERE key=?", (key,)
                ).fetchone()
                if row:
                    db.execute("UPDATE entry SET used=? WHERE key=?", (now, key))
                return row
        finally:
            db.close()

    def put(self, key: str, body: bytes, now: float) -> None:
        if len(body) > self.payload_bytes:
            return
        db = self.connect()
        try:
            with db:
                db.execute("DELETE FROM entry WHERE key=?", (key,))
                while True:
                    count, size = db.execute(
                        "SELECT count(*),coalesce(sum(length(body)),0) FROM entry"
                    ).fetchone()
                    if count < self.entries and size + len(body) <= self.payload_bytes:
                        break
                    db.execute(
                        "DELETE FROM entry WHERE key=(SELECT key FROM entry ORDER BY used,key LIMIT 1)"
                    )
                db.execute("INSERT INTO entry VALUES(?,?,?,?)", (key, body, now, now))
        finally:
            db.close()

    def clear(self) -> None:
        with closing(self.connect()) as db, db:
            db.execute("DELETE FROM entry")

    def floor(self, scope: str) -> int:
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT revision FROM revision_floor WHERE scope=?", (scope,)
            ).fetchone()
            return row[0] if row else 0

    def accept(self, scope: str, revision: int) -> None:
        with closing(self.connect()) as db, db:
            row = db.execute(
                "SELECT revision FROM revision_floor WHERE scope=?", (scope,)
            ).fetchone()
            if row and row[0] > revision:
                raise ValueError("response revision regressed")
            db.execute(
                "INSERT INTO revision_floor VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET revision=max(revision,excluded.revision)",
                (scope, revision),
            )
            # Source/auth switches cannot grow private cache state indefinitely.
            db.execute(
                "DELETE FROM revision_floor WHERE scope IN (SELECT scope FROM revision_floor ORDER BY rowid DESC LIMIT -1 OFFSET 128)"
            )


class Client:
    def __init__(
        self,
        origin: str,
        source_id: str,
        token: str,
        cache: Cache,
        *,
        ttl_s: float = 60,
        stale_s: float = 86400,
        deadline_s: float = 3,
        transport: httpx.AsyncBaseTransport | None = None,
        allow_private_http: bool = False,
    ) -> None:
        url = urlsplit(origin)
        if url.scheme != "https" and not (
            url.scheme == "http"
            and (url.hostname in {"127.0.0.1", "localhost"} or allow_private_http)
        ):
            raise ValueError("HTTPS or explicit loopback required")
        if (
            not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in ("", "/")
        ):
            raise ValueError("invalid metadata origin")
        self.origin, self.source_id, self.cache = origin.rstrip("/"), source_id, cache
        self.ttl_s, self.stale_s, self.deadline_s = ttl_s, stale_s, deadline_s
        self.auth_context = hashlib.sha256(token.encode()).hexdigest()
        self.http = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(deadline_s, connect=min(1, deadline_s)),
            trust_env=False,
            follow_redirects=False,
            headers={"Authorization": "Bearer " + token, "Accept-Encoding": "identity"},
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=8),
        )
        self.pending: dict[str, asyncio.Task[Result]] = {}
        self.waiters = 0
        self.requests = self.response_bytes = self.hits = self.stale_hits = 0

    async def close(self) -> None:
        for task in self.pending.values():
            task.cancel()
        await asyncio.gather(*self.pending.values(), return_exceptions=True)
        await self.http.aclose()

    def key(self, request: Request) -> str:
        return hashlib.sha256(
            dumps(
                [
                    1,
                    self.origin,
                    self.source_id,
                    self.auth_context,
                    request.model_dump(),
                ]
            )
        ).hexdigest()

    async def _fetch(self, request: Request, *, now: float | None = None) -> Result:
        now = time.time() if now is None else now
        key = self.key(request)
        try:
            cached = self.cache.get(key, now)
        except (sqlite3.Error, ValueError):
            cached = None
        old = None
        age = 0.0
        if cached:
            try:
                old = Response.model_validate(loads(cached[0], MAX_RESPONSE))
                old.check_request(request, self.source_id)
                if old.revision < self.cache.floor(
                    self.auth_context + self.origin + self.source_id
                ):
                    raise ValueError("cached revision regressed")
                age = now - cached[1]
                if 0 <= age < self.ttl_s:
                    self.hits += 1
                    return Result(old, "hit", age)
            except (ValueError, TypeError, sqlite3.Error):
                old = None  # Corrupt cache cannot become an outage answer.
        error = "invalid_response"
        try:
            self.requests += 1
            async with asyncio.timeout(self.deadline_s):
                async with self.http.stream(
                    "POST",
                    self.origin + "/catalog/v1/query",
                    json=request.model_dump(),
                ) as response:
                    if response.status_code != 200:
                        error = f"http_{response.status_code}"
                        raise Unavailable(error)
                    if (
                        response.headers.get("content-type", "").split(";")[0]
                        != "application/json"
                    ):
                        raise ValueError("response content type")
                    if (
                        response.headers.get("content-encoding", "identity")
                        != "identity"
                    ):
                        raise ValueError("compressed response unsupported")
                    body = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=16384):
                        self.response_bytes += len(chunk)
                        body.extend(chunk)
                        if len(body) > MAX_RESPONSE:
                            raise ValueError("response too large")
                result = Response.model_validate(loads(bytes(body), MAX_RESPONSE))
                result.check_request(request, self.source_id)
                scope = self.auth_context + self.origin + self.source_id
                if result.revision < self.cache.floor(scope):
                    raise ValueError("response revision regressed")
                try:
                    self.cache.accept(scope, result.revision)
                    self.cache.put(key, bytes(body), now)
                except sqlite3.Error:
                    return Result(result, "miss", 0, "cache_unavailable")
                return Result(result, "miss", 0)
        except (
            httpx.HTTPError,
            TimeoutError,
            Unavailable,
            ValueError,
            TypeError,
        ) as exc:
            if isinstance(exc, (TimeoutError, httpx.TimeoutException)):
                error = "timeout"
            elif isinstance(exc, httpx.HTTPError):
                error = "transport"
            # Empty results are useful only on a successful current fetch. Do
            # not mask an outage with a previously cached negative response.
            eligible = error in {"transport", "timeout", "http_503", "http_429"}
            if (
                eligible
                and old is not None
                and old.total > 0
                and 0 <= age <= self.stale_s
            ):
                self.stale_hits += 1
                return Result(old, "stale", age, error)
            raise Unavailable(error) from exc

    async def fetch(self, request: Request, *, now: float | None = None) -> Result:
        """Share one same-key miss; cancellation belongs to each waiter."""
        key = self.key(request)
        if self.waiters >= 64:
            raise Unavailable("client_busy")
        task = self.pending.get(key)
        if task is None:
            if len(self.pending) >= 8:
                raise Unavailable("client_busy")
            task = asyncio.create_task(self._fetch(request, now=now))
            self.pending[key] = task

            def settled(done: asyncio.Task[Result]) -> None:
                self.pending.pop(key, None)
                if not done.cancelled():
                    done.exception()  # A cancelled sole waiter must not leak an error log.

            task.add_done_callback(settled)
        self.waiters += 1
        try:
            return await asyncio.shield(task)
        finally:
            self.waiters -= 1
