"""Authenticated bounded metadata serving inside the collector project."""

import asyncio
import hmac
import json
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import ClassVar

from catalog_core.diagnostics import reason
from catalog_core.json_codec import ContractError, loads
from catalog_core.protocol import MAX_RESPONSE, Request
from fastapi import FastAPI
from fastapi import Request as HTTPRequest
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .query_reader import execute


class Admission:
    """Global budget plus bounded per-source and per-operation sub-budgets.

    Per-token fairness is impossible with the pilot's single shared bearer
    token, so that is intentionally not attempted. Remote address is used only
    for fairness, never logging; behind a proxy every request shares the proxy
    address and therefore falls back to the global and per-operation caps.
    A per-source active cap prevents one address from occupying all eight
    global slots across operations; operation caps still keep a native flood
    from starving title discovery.
    """

    OPERATIONS: ClassVar[dict[str, int]] = {
        "titles": 2,
        "native": 4,
        "recent": 4,
    }
    CLIENTS = 64
    CLIENT_ACTIVE = 4
    CLIENT_RATE = 100.0
    CLIENT_BURST = 128

    def __init__(self, rate: float = 200, burst: int = 256) -> None:
        self.rate, self.burst = rate, burst
        self.tokens = float(burst)
        self.at = time.monotonic()
        self.active = 0
        self.clients: dict[str, tuple[float, float]] = {}
        self.client_active: dict[str, int] = {}
        self.operations = dict.fromkeys(self.OPERATIONS, 0)

    def _client_tokens(self, client: str, now: float) -> tuple[float, float]:
        tokens, at = self.clients.get(client, (float(self.CLIENT_BURST), now))
        tokens = min(self.CLIENT_BURST, tokens + (now - at) * self.CLIENT_RATE)
        return tokens, now

    def enter(self, client: str, operation: str) -> bool:
        now = time.monotonic()
        self.tokens = min(self.burst, self.tokens + (now - self.at) * self.rate)
        self.at = now
        client_tokens, at = self._client_tokens(client, now)
        limit = self.OPERATIONS.get(operation)
        if (
            limit is None
            or self.active >= 8
            or self.operations[operation] >= limit
            or self.client_active.get(client, 0) >= self.CLIENT_ACTIVE
            or self.tokens < 1
            or client_tokens < 1
        ):
            # Age a denied client bucket without consuming a global token.
            self.clients[client] = (client_tokens, at)
            self._trim_clients()
            return False
        self.tokens -= 1
        self.clients[client] = (client_tokens - 1, at)
        self.client_active[client] = self.client_active.get(client, 0) + 1
        self.operations[operation] += 1
        self.active += 1
        self._trim_clients()
        return True

    def _trim_clients(self) -> None:
        if len(self.clients) <= self.CLIENTS:
            return
        # Never drop an active counter: leave() is keyed by the same address and
        # must release exactly the slot that enter() reserved.
        for client in sorted(self.clients, key=lambda key: self.clients[key][1]):
            if self.client_active.get(client, 0):
                continue
            del self.clients[client]
            if len(self.clients) <= self.CLIENTS:
                break

    def leave(self, client: str, operation: str) -> None:
        self.active = max(0, self.active - 1)
        if operation in self.operations:
            self.operations[operation] = max(0, self.operations[operation] - 1)
        active = self.client_active.get(client, 0)
        if active:
            if active == 1:
                del self.client_active[client]
            else:
                self.client_active[client] = active - 1


def create_app(
    root: Path,
    token: str,
    *,
    now: int | None = None,
    rate: float = 200,
    burst: int = 256,
) -> FastAPI:
    """Serve only the operator-owned read catalog; queries never collect."""
    if len(token) < 16:
        raise ValueError("use a token of at least 16 characters")
    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None)
    admission = Admission(rate, burst)
    app.state.admission = admission
    app.state.completed = 0
    app.state.bytes = 0

    def error(status: int, code: str) -> JSONResponse:
        return JSONResponse(
            {"error": code},
            status_code=status,
            headers={"Cache-Control": "no-store", "Retry-After": "1"},
        )

    @app.post("/catalog/v1/query")
    async def metadata(http: HTTPRequest) -> JSONResponse:
        if not hmac.compare_digest(
            http.headers.get("authorization", "").encode(), ("Bearer " + token).encode()
        ):
            return error(401, "unauthorized")
        cancel = threading.Event()
        work = None
        validated = False
        admitted = False
        request = None
        client = "unknown"
        operation = "titles"
        started = time.monotonic()

        def diagnostic(exc: BaseException):
            code = (
                "catalog_busy"
                if isinstance(exc, TimeoutError) and str(exc) == "catalog_busy"
                else reason(exc)
            )
            code = (
                "query_deadline"
                if isinstance(exc, ContractError) and str(exc) == "query_deadline"
                else code
            )
            logging.getLogger("catalog.query").warning(
                json.dumps(
                    {
                        "stage": "query",
                        "reason": code,
                        "error_class": type(exc).__name__,
                        "provider": request.provider if request else None,
                        "operation": request.operation if request else None,
                        "duration_s": round(time.monotonic() - started, 4),
                    },
                    separators=(",", ":"),
                )
            )

        try:
            async with asyncio.timeout(3):
                body = bytearray()
                async for chunk in http.stream():
                    body.extend(chunk)
                    if len(body) > 16384:
                        return error(413, "request_too_large")
                request = Request.model_validate(loads(bytes(body), 16384))
                validated = True
                operation = request.operation
                client = http.client.host if http.client else "unknown"
                if not admission.enter(client, operation):
                    return error(429, "admission_busy")
                admitted = True
                # to_thread prevents SQLite from blocking unrelated HTTP. On
                # timeout/disconnect the progress handler stops SQL, and the slot
                # remains owned until the thread has actually settled.
                work = asyncio.create_task(
                    asyncio.to_thread(
                        execute,
                        root,
                        request,
                        int(time.time()) if now is None else now,
                        cancel,
                    )
                )
                while not work.done():
                    if await http.is_disconnected():
                        cancel.set()
                        raise asyncio.CancelledError
                    await asyncio.wait({work}, timeout=0.02)
                response = work.result()
                raw = response.model_dump_json().encode()
                if len(raw) > MAX_RESPONSE:
                    return error(503, "response_too_large")
                app.state.completed += 1
                app.state.bytes += len(raw)
                return JSONResponse(
                    response.model_dump(), headers={"Cache-Control": "no-store"}
                )
        except (ValidationError, ContractError, ValueError) as exc:
            if isinstance(exc, ContractError) and str(exc) == "query_too_broad":
                return error(400, "query_too_broad")
            if validated:
                diagnostic(exc)
            return (
                error(503, "catalog_unavailable")
                if validated
                else error(400, "invalid_request")
            )
        except (OSError, sqlite3.Error, TimeoutError) as exc:
            diagnostic(exc)
            return error(503, "catalog_unavailable")
        finally:
            cancel.set()
            if work is not None:
                try:
                    await asyncio.shield(work)
                except Exception, asyncio.CancelledError:  # noqa: BLE001,S110 -- cancellation settles SQL; no raw query diagnostics
                    pass
            if admitted:
                admission.leave(client, operation)

    return app
