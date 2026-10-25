"""Bound unauthenticated form input before the framework's normal parser."""

import asyncio

from starlette.requests import ClientDisconnect, Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import Message, Receive, Scope

LOGIN_BYTES = 16 * 1024
LOGIN_FRAMES = 1024
LOGIN_DEADLINE_S = 5


class ExcessiveFrames(Exception):
    """Bound empty ASGI messages that Request.stream would otherwise hide."""


def rejected(status: int) -> Response:
    return PlainTextResponse(
        "Invalid login request",
        status_code=status,
        headers={"Cache-Control": "no-store"},
    )


async def bounded_receive(scope: Scope, receive: Receive) -> Receive | Response:
    frames = 0

    async def guarded_receive() -> Message:
        nonlocal frames
        frames += 1
        if frames > LOGIN_FRAMES:
            raise ExcessiveFrames
        return await receive()

    request = Request(scope, guarded_receive)
    length = request.headers.get("content-length")
    if length is not None:
        if len(length) > 8 or not length.isascii() or not length.isdecimal():
            return rejected(400)
        if int(length) > LOGIN_BYTES:
            return rejected(413)
    body = bytearray()
    try:
        async with asyncio.timeout(LOGIN_DEADLINE_S):
            async for chunk in request.stream():
                if len(body) + len(chunk) > LOGIN_BYTES:
                    return rejected(413)
                body.extend(chunk)
    except TimeoutError:
        return rejected(408)
    except ClientDisconnect:
        return rejected(400)
    except ExcessiveFrames:
        return rejected(413)
    payload = bytes(body)
    delivered = False

    async def replay() -> Message:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": payload, "more_body": False}
        return await receive()

    return replay
