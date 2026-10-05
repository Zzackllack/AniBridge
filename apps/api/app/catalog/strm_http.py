"""Stable STRM URLs bound to durable accepted requests, resolved user-locally."""

import asyncio
import hashlib
import json
import tempfile
import threading
from contextlib import closing
from pathlib import Path
from uuid import UUID

from catalog_core.files import atomic_write
from catalog_core.json_codec import dumps, loads
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask

from app.core.strm_proxy.auth import build_auth_params, require_auth
from app.core.strm_proxy.hls import rewrite_hls_playlist
from app.core.strm_proxy.urls import _build_url

from .child_budget import CONSUMER_CHILDREN
from .executor import SubprocessExecutor
from .jobs import JobError
from .stream_transport import open_stream, target

router = APIRouter()


def stream_url(job_id: str, upstream: str | None = None) -> str:
    params = {"job": job_id, "ab_scope": "catalog-playback-1"}
    if upstream is not None:
        target(upstream)
        params["u"] = upstream
    # Top-level files stay stable; nested resources use the existing expiring
    # signature policy and never enter the catalog or a hosted worker.
    params.update(build_auth_params(params, include_exp=upstream is not None))
    return _build_url("/strm/catalog", params)


class Playback:
    def __init__(
        self, store, jobs, origins: dict[str, str], hosts: tuple[str, ...]
    ) -> None:
        self.store, self.jobs, self.origins, self.hosts = store, jobs, origins, hosts
        self.slots = threading.BoundedSemaphore(2)
        self.executor = SubprocessExecutor(origins, hosts, jobs.download_dir)
        self.opened = set()
        self.resolving = set()

    async def resolve(self, payload: dict) -> str:
        lease = CONSUMER_CHILDREN.try_acquire("validation")
        if lease is None:
            raise HTTPException(
                503, "Resolution capacity unavailable", headers={"Retry-After": "60"}
            )
        task = asyncio.current_task()
        self.resolving.add(task)
        try:
            with tempfile.TemporaryDirectory(
                prefix="playback-", dir=self.store.directory
            ) as directory:
                root = Path(directory)
                source, result = root / "request", root / "result"
                atomic_write(
                    source,
                    dumps(
                        {
                            "payload": payload,
                            "origin": self.origins[payload["provider"]],
                            "hosts": payload.get("host_preference") or list(self.hosts),
                        }
                    ),
                )
                code = await self.executor._run(
                    "app.catalog.resolve_child",
                    [str(source), str(result), str(root)],
                    deadline=60,
                )
                if code or not result.is_file() or result.stat().st_size > 65536:
                    raise HTTPException(502, "Source resolution unavailable")
                value = loads(result.read_bytes(), 65536)
                if value.get("outcome") != "ok":
                    raise HTTPException(502, "Source resolution unavailable")
                target(value.get("url"))
                return value["url"]
        except OSError, ValueError, TimeoutError:
            raise HTTPException(502, "Source resolution unavailable") from None
        finally:
            lease.close()
            self.resolving.discard(task)

    def accepted(self, job_id: str) -> dict:
        record = self.jobs.get(job_id)
        payload = json.loads(record["payload"] or "null")
        if (
            not payload
            or payload.get("mode") != "strm"
            or payload.get("strm_delivery") != "proxy"
        ):
            raise HTTPException(409, "Stream was not registered")
        with closing(self.jobs.db()) as db:
            registration = db.execute(
                "SELECT body FROM catalog_cache WHERE kind='strm_proxy' AND key=?",
                (job_id,),
            ).fetchone()
        digest = hashlib.sha256(record["payload"].encode()).hexdigest()
        if (
            registration is None
            or json.loads(registration[0]).get("payload_digest") != digest
        ):
            raise HTTPException(409, "Stream was not registered")
        return payload

    async def close(self) -> None:
        tasks = list(self.resolving)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        for opened in list(self.opened):
            await opened.close()
        self.opened.clear()

    async def serve(self, request: Request, job_id: str, upstream: str | None):
        if not self.slots.acquire(blocking=False):
            raise HTTPException(
                503, "Playback capacity unavailable", headers={"Retry-After": "60"}
            )
        opened, released = None, False

        async def close() -> None:
            nonlocal released
            try:
                if opened is not None:
                    self.opened.discard(opened)
                    await opened.close()
            finally:
                if not released:
                    self.slots.release()
                    released = True

        try:
            try:
                payload = await asyncio.to_thread(self.accepted, job_id)
            except JobError:
                raise HTTPException(404, "Unknown stream") from None
            if payload["provider"] not in self.origins:
                raise HTTPException(403, "Provider is disabled")
            url = upstream if upstream is not None else await self.resolve(payload)
            opened = await open_stream(
                url, request.method, request.headers.get("range")
            )
            self.opened.add(opened)
            if request.method == "HEAD":
                response = Response(
                    b"", status_code=opened.response.status_code, headers=opened.headers
                )
                await close()
                return response
            if opened.playlist and opened.response.status_code == 200:
                body = await opened.playlist_body()
                if not body.lstrip().startswith(b"#EXTM3U"):
                    raise HTTPException(502, "Invalid upstream playlist")
                count = 0

                def nested(url: str) -> str:
                    nonlocal count
                    count += 1
                    if count > 4096:
                        raise HTTPException(502, "Upstream playlist exceeds capacity")
                    return stream_url(job_id, url)

                rewritten = rewrite_hls_playlist(
                    body.decode("utf-8", errors="strict"),
                    base_url=opened.url,
                    rewrite_url=nested,
                ).encode()
                if len(rewritten) > 8 * 1024**2:
                    raise HTTPException(502, "Rewritten playlist exceeds capacity")
                headers = {
                    key: value
                    for key, value in opened.headers.items()
                    if key
                    not in ("content-length", "content-range", "etag", "last-modified")
                }
                headers["content-type"] = "application/vnd.apple.mpegurl"
                await close()
                return Response(rewritten, headers=headers)

            async def body():
                try:
                    async for block in opened.body():
                        yield block
                finally:
                    await close()

            return StreamingResponse(
                body(),
                status_code=opened.response.status_code,
                headers=opened.headers,
                background=BackgroundTask(close),
            )
        except BaseException as exc:
            await close()
            if isinstance(exc, (UnicodeError, TimeoutError, ValueError)):
                raise HTTPException(502, "Upstream stream unavailable") from None
            raise


@router.api_route("/strm/catalog", methods=["GET", "HEAD"])
async def stream(request: Request):
    params = dict(request.query_params)
    if len(params) != len(request.query_params.multi_items()) or set(params) - {
        "job",
        "u",
        "sig",
        "exp",
        "apikey",
        "ab_scope",
    }:
        raise HTTPException(400, "Invalid stream request")
    require_auth(params, scope="catalog-playback-1")
    job_id = params.get("job", "")
    try:
        if UUID(job_id).hex != job_id:
            raise ValueError("job identity")
    except ValueError:
        raise HTTPException(400, "Invalid stream identity") from None
    runtime = getattr(request.app.state, "catalog", None)
    if runtime is None:
        raise HTTPException(503, "Catalog playback unavailable")
    return await runtime.playback.serve(request, job_id, params.get("u"))
