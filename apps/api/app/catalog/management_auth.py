"""Independent bearer authorization and bounded management request admission."""

import base64
import hmac
import re
import time
from collections import deque

from catalog_core.json_codec import loads
from fastapi import Request
from fastapi.responses import JSONResponse


class ManagementError(Exception):
    def __init__(
        self, code: str, status: int, message: str, retryable: bool = False
    ) -> None:
        self.code, self.status, self.message, self.retryable = (
            code,
            status,
            message,
            retryable,
        )

    def response(self) -> JSONResponse:
        headers = {}
        if self.status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        if self.status in (429, 503):
            headers["Retry-After"] = "60"
        return JSONResponse(
            {
                "error": {
                    "code": self.code,
                    "message": self.message,
                    "retryable": self.retryable,
                }
            },
            status_code=self.status,
            headers=headers,
        )


def validate_token(value: str | None) -> str | None:
    if not value:
        return None
    if not re.fullmatch(r"[A-Za-z0-9_-]{43,342}={0,2}", value):
        raise ValueError(
            "MANAGEMENT_API_TOKEN must encode at least 32 random bytes as base64url"
        )
    decoded = base64.b64decode(
        value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
    )
    if len(decoded) < 32:
        raise ValueError(
            "MANAGEMENT_API_TOKEN must encode at least 32 random bytes as base64url"
        )
    return value


class ManagementAuth:
    def __init__(
        self, token: str | None, origins: tuple[str, ...] = (), clock=time.monotonic
    ) -> None:
        self.token, self.origins, self.clock = validate_token(token), origins, clock
        self.mutations: deque[float] = deque()

    async def check(self, request: Request) -> dict | None:
        if self.token is None:
            raise ManagementError(
                "management_disabled", 503, "Management API is disabled"
            )
        scheme, _, supplied = request.headers.get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not hmac.compare_digest(
            supplied.encode(), self.token.encode()
        ):
            raise ManagementError("unauthorized", 401, "Authentication required")
        if request.method in ("GET", "HEAD"):
            return None
        origin = request.headers.get("origin")
        if origin is not None and (origin == "null" or origin not in self.origins):
            raise ManagementError("unauthorized", 403, "Origin is not allowed")
        now = self.clock()
        while self.mutations and self.mutations[0] <= now - 60:
            self.mutations.popleft()
        if len(self.mutations) >= 60:
            raise ManagementError("rate_limited", 429, "Mutation rate exceeded", True)
        self.mutations.append(now)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 16384:
                raise ManagementError(
                    "invalid_request", 400, "Request body is too large"
                )
        if request.method == "DELETE":
            if body:
                raise ManagementError(
                    "invalid_request", 400, "DELETE requires an empty body"
                )
            return None
        try:
            data = loads(bytes(body), 16384)
            if type(data) is not dict:
                raise ValueError("object required")
            return data
        except ValueError:
            raise ManagementError("invalid_request", 400, "Invalid JSON body") from None


def version(request: Request) -> int:
    value = request.headers.get("if-match")
    if value is None:
        raise ManagementError("precondition_required", 428, "If-Match is required")
    if not re.fullmatch(r'"[1-9][0-9]{0,18}"', value):
        raise ManagementError("version_conflict", 412, "Resource changed")
    return int(value[1:-1])
