"""Optional qBittorrent credentials and signed, expiring sessions."""

from __future__ import annotations

import hashlib
import hmac
import time
from collections import deque

from fastapi import FastAPI
from starlette.datastructures import MutableHeaders
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import HTTPConnection
from starlette.responses import PlainTextResponse
from starlette.types import ASGIApp, Receive, Scope, Send, Message


class QbitAuth:
    def __init__(
        self,
        username: str = "",
        password: str = "",
        secret: str = "",
        secure: bool = False,
    ) -> None:
        configured = bool(username or password or secret)
        if configured and not (
            1 <= len(username.encode()) <= 256
            and 16 <= len(password.encode()) <= 1024
            and 32 <= len(secret.encode()) <= 512
        ):
            raise ValueError(
                "Set QBIT_USERNAME, QBIT_PASSWORD (16+ bytes) and "
                "QBIT_SESSION_SECRET (32+ random bytes) together"
            )
        self.enabled, self.username, self.password, self.secure = (
            configured,
            username,
            password,
            secure,
        )
        # Rotate credentials or the independent random secret to invalidate all
        # sessions across workers/restarts without storing passwords in cookies.
        self.signing_key = hmac.new(
            secret.encode(),
            username.encode() + b"\0" + password.encode(),
            hashlib.sha256,
        ).hexdigest()
        self.attempts: deque[float] = deque(maxlen=60)

    def admit_login(self) -> int:
        now = time.monotonic()
        while self.attempts and self.attempts[0] <= now - 60:
            self.attempts.popleft()
        if len(self.attempts) == 60:
            return max(1, int(self.attempts[0] + 60 - now) + 1)
        # Reserve on the event loop, before reading forms or dispatching a sync
        # handler. Concurrent bad logins cannot all pass a post-failure counter.
        self.attempts.append(now)
        return 0

    def credentials_match(self, username: str, password: str) -> bool:
        user_ok = hmac.compare_digest(username.encode(), self.username.encode())
        password_ok = hmac.compare_digest(password.encode(), self.password.encode())
        return user_ok & password_ok


class QbitAuthMiddleware:
    def __init__(self, app: ASGIApp, auth: QbitAuth) -> None:
        self.app, self.auth = app, auth
        self.sessions = SessionMiddleware(
            self.guard,
            auth.signing_key,
            session_cookie="SID",
            max_age=3600,
            path="/api/v2",
            same_site="strict",
            https_only=auth.secure,
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if (
            scope["type"] == "http"
            and self.auth.enabled
            and (path == "/api/v2" or path.startswith("/api/v2/"))
        ):
            await self.sessions(scope, receive, send)
        else:
            await self.app(scope, receive, send)

    async def guard(self, scope: Scope, receive: Receive, send: Send) -> None:
        connection = HTTPConnection(scope)
        login = scope["path"] == "/api/v2/auth/login"
        origin = connection.headers.get("origin")
        if (
            scope["method"] not in ("GET", "HEAD")
            and origin is not None
            and origin != str(connection.url.replace(path="", query=""))
        ):
            response = PlainTextResponse(
                "Forbidden", status_code=403, headers={"Cache-Control": "no-store"}
            )
        elif login and (delay := self.auth.admit_login()):
            response = PlainTextResponse(
                "Too many login attempts",
                status_code=429,
                headers={"Retry-After": str(delay), "Cache-Control": "no-store"},
            )
        elif not login and connection.session.get("authenticated") is not True:
            response = PlainTextResponse(
                "Forbidden", status_code=403, headers={"Cache-Control": "no-store"}
            )
        else:

            async def private_send(message: Message) -> None:
                if message["type"] == "http.response.start":
                    MutableHeaders(scope=message)["Cache-Control"] = "no-store"
                await send(message)

            await self.app(scope, receive, private_send)
            return
        await response(scope, receive, send)


def install(app: FastAPI, auth: QbitAuth) -> None:
    app.state.qbit_auth = auth
    app.add_middleware(QbitAuthMiddleware, auth=auth)
