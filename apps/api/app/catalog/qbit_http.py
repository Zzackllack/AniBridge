"""qBittorrent routes sharing durable job state; handlers never extract media."""

# FastAPI uses these dependency defaults to inject the existing DB session.
# ruff: noqa: B008

import json
import sqlite3
import time
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from app.db import get_session

from .http import runtime
from .jobs import JobError

if TYPE_CHECKING:
    from .runtime import Runtime

router = APIRouter(prefix="/api/v2")


async def form(request: Request) -> dict[str, str]:
    if (
        request.headers.get("content-type", "").split(";", 1)[0]
        != "application/x-www-form-urlencoded"
    ):
        raise HTTPException(400, "invalid form")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 128 * 1024:
            raise HTTPException(400, "form too large")
    try:
        fields = parse_qs(
            body.decode("utf-8"),
            max_num_fields=32,
            keep_blank_values=True,
            strict_parsing=True,
        )
        if any(len(values) != 1 for values in fields.values()):
            raise ValueError("duplicate field")
        return {key: values[0] for key, values in fields.items()}
    except ValueError, UnicodeError:
        raise HTTPException(400, "invalid form") from None


def boolean(value: str) -> bool:
    # .NET clients use Convert.ToString(bool), producing True/False.
    value = value.lower()
    if value not in ("true", "false", "1", "0", ""):
        raise JobError("invalid_request", 400)
    return value in ("true", "1")


def reject(exc: ValueError):
    status = exc.status if isinstance(exc, JobError) else 400
    raise HTTPException(
        status,
        exc.code if isinstance(exc, JobError) else "invalid_request",
        headers={"Retry-After": "60"} if status in (429, 503) else None,
    ) from None


@router.post("/torrents/add")
async def add(request: Request):
    service = runtime(request)
    data = await form(request)
    try:
        await run_in_threadpool(
            service.jobs.admit,
            data.get("urls", ""),
            int(time.time()),
            paused=boolean(data.get("paused", "false")),
            savepath=data.get("savepath") or None,
            category=data.get("category"),
            mapping_check=service.mapping_check,
            legacy_path=service.legacy_path,
        )
    except ValueError as exc:
        reject(exc)
    except sqlite3.Error:
        reject(JobError("catalog_busy", 503))
    return PlainTextResponse("Ok.")


def rows(
    service: "Runtime", filter: str | None = None, category: str | None = None
) -> Iterator[dict]:
    # Preserve the released projection for untouched legacy records. Durable
    # records use the lifecycle projection; neither path retains the full history.
    yield from service.client.views(
        durable=False, category=category if category else None
    )
    for row in service.client.views(category=category):
        if filter == "completed" and row["progress"] != 1:
            continue
        if filter in ("downloading", "incomplete") and row["progress"] == 1:
            continue
        yield row


def json_chunks(pieces: Iterable[str]) -> Iterator[bytes]:
    """Bound encoding buffers while avoiding a threadpool hop per tiny token."""
    buffer = ""
    for piece in pieces:
        buffer += piece
        if len(buffer) >= 32768:
            yield buffer.encode()
            buffer = ""
    if buffer:
        yield buffer.encode()


def info_json(
    service: "Runtime", filter: str | None, category: str | None
) -> Iterator[str]:
    yield "["
    separator = ""
    for row in rows(service, filter, category):
        yield separator + json.dumps(row, separators=(",", ":"))
        separator = ","
    yield "]"


@router.get("/torrents/info")
def info(request: Request, filter: str | None = None, category: str | None = None):
    return StreamingResponse(
        json_chunks(info_json(runtime(request), filter, category)),
        media_type="application/json",
    )


@router.get("/sync/maindata")
def sync(request: Request):
    from app.api.qbittorrent.common import CATEGORIES

    service = runtime(request)

    def pieces() -> Iterator[str]:
        yield '{"rid":1,"full_update":true,"server_state":{"connection_status":"connected","dht_nodes":0},"torrents":{'
        separator = ""
        for row in rows(service):
            yield (
                separator
                + json.dumps(row["hash"])
                + ":"
                + json.dumps(row, separators=(",", ":"))
            )
            separator = ","
        yield '},"categories":' + json.dumps(CATEGORIES) + "}"

    return StreamingResponse(json_chunks(pieces()), media_type="application/json")


def selected(request: Request, value: str) -> dict | None:
    try:
        rows = runtime(request).client.aliases(value)
        return rows[0] if rows else None
    except JobError as exc:
        reject(exc)


@router.get("/torrents/files")
def files(request: Request, hash: str = "", session: Session = Depends(get_session)):
    alias = selected(request, hash)
    if alias is None:
        from app.api.qbittorrent.torrents import torrents_files

        return torrents_files(session=session, hash=hash)
    view = runtime(request).client.view(alias)
    job = runtime(request).jobs.get(alias["job_id"])
    if (
        not view["content_path"]
        or not job["result_path"]
        or not Path(job["result_path"]).is_file()
    ):
        return []
    return [
        {
            "index": 0,
            "name": Path(job["result_path"]).name,
            "size": Path(job["result_path"]).stat().st_size,
            "progress": view["progress"],
            "priority": 1,
            "is_seed": view["progress"] == 1,
        }
    ]


@router.get("/torrents/properties")
def properties(
    request: Request, hash: str = "", session: Session = Depends(get_session)
):
    alias = selected(request, hash)
    if alias is None:
        from app.api.qbittorrent.torrents import torrents_properties

        return torrents_properties(session=session, hash=hash)
    view = runtime(request).client.view(alias)
    return {
        "save_path": view["save_path"],
        "creation_date": view["added_on"],
        "addition_date": view["added_on"],
        "completion_date": view["completion_on"],
        "piece_size": 1,
        "pieces_num": 1,
        "pieces_have": int(view["progress"] == 1),
        "total_downloaded": view["downloaded"],
        "total_downloaded_session": view["downloaded"],
        "total_uploaded": 0,
        "total_uploaded_session": 0,
        "total_wasted": 0,
        "share_ratio": 0,
        "dl_limit": 0,
        "up_limit": 0,
        "dl_speed_avg": 0,
        "up_speed_avg": 0,
        "time_elapsed": max(0, int(time.time()) - view["added_on"]),
        "seeding_time": 0,
        "nb_connections": 0,
        "nb_connections_limit": 0,
        "created_by": "AniBridge",
        "last_seen": 0,
        "total_seen": 0,
    }


@router.post("/torrents/pause")
@router.post("/torrents/resume")
async def transition(request: Request):
    service = runtime(request)
    data = await form(request)
    action = request.url.path.rsplit("/", 1)[-1]
    try:
        await run_in_threadpool(
            service.client.transition, data.get("hashes", ""), action, int(time.time())
        )
    except JobError as exc:
        reject(exc)
    except sqlite3.Error:
        reject(JobError("catalog_busy", 503))
    return PlainTextResponse("Ok.")


@router.post("/torrents/delete")
async def delete(request: Request, session: Session = Depends(get_session)):
    service = runtime(request)
    data = await form(request)
    try:
        await run_in_threadpool(remove, service, session, data)
    except ValueError as exc:
        reject(exc)
    except sqlite3.Error:
        reject(JobError("catalog_busy", 503))
    return PlainTextResponse("Ok.")


def remove(service, session: Session, data: dict[str, str]) -> None:
    from app.api.qbittorrent.torrents import torrents_delete
    from app.config import DELETE_FILES_ON_TORRENT_DELETE

    hashes = data.get("hashes", "")
    from .client import hash_values

    hash_values(hashes)  # Validate before creating any deletion intent.
    delete_files = (
        boolean(data.get("deleteFiles", "false")) or DELETE_FILES_ON_TORRENT_DELETE
    )
    service.client.remove(hashes, delete_files, int(time.time()))
    for batch in service.client.alias_batches(hashes, durable=False):
        torrents_delete(
            session=session,
            hashes="|".join(row["hash"] for row in batch),
            deleteFiles=delete_files,
        )
