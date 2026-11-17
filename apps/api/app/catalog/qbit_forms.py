"""Bounded URL-encoded and multipart forms for query-mode qBittorrent routes."""

import asyncio
from urllib.parse import parse_qs

from fastapi import HTTPException, Request
from starlette.formparsers import parse_options_header
from starlette.requests import ClientDisconnect
from starlette.types import Message

FORM_MAX_BYTES = 128 * 1024
FORM_MAX_FIELDS = 32
FORM_MAX_FRAMES = 1024
FORM_DEADLINE_S = 5


async def _bounded_body(request: Request) -> bytes:
    length = request.headers.get("content-length")
    if length is not None:
        if len(length) > 8 or not length.isascii() or not length.isdecimal():
            raise HTTPException(400, "invalid form")
        if int(length) > FORM_MAX_BYTES:
            raise HTTPException(400, "form too large")

    body = bytearray()
    frames = 0
    try:
        async with asyncio.timeout(FORM_DEADLINE_S):
            while True:
                frames += 1
                if frames > FORM_MAX_FRAMES:
                    raise HTTPException(400, "form too large")
                message = await request.receive()
                if message["type"] == "http.disconnect":
                    raise ClientDisconnect
                if message["type"] != "http.request":
                    raise HTTPException(400, "invalid form")
                chunk = message.get("body", b"")
                if len(body) + len(chunk) > FORM_MAX_BYTES:
                    raise HTTPException(400, "form too large")
                body.extend(chunk)
                if not message.get("more_body", False):
                    break
    except TimeoutError:
        raise HTTPException(408, "invalid form") from None
    except ClientDisconnect:
        raise HTTPException(400, "invalid form") from None

    if length is not None and len(body) != int(length):
        raise HTTPException(400, "invalid form")
    result = bytes(body)
    try:
        result.decode("utf-8")
    except UnicodeError:
        raise HTTPException(400, "invalid form") from None
    return result


async def form(request: Request) -> dict[str, str]:
    try:
        content_type, options = parse_options_header(
            request.headers.get("content-type")
        )
    except TypeError, ValueError:
        raise HTTPException(400, "invalid form") from None
    if content_type not in (
        b"application/x-www-form-urlencoded",
        b"multipart/form-data",
    ):
        raise HTTPException(400, "invalid form")
    body = await _bounded_body(request)

    if content_type == b"multipart/form-data":
        boundary = options.get(b"boundary")
        if not boundary or len(boundary) > 70:
            raise HTTPException(400, "invalid form")
        closing = b"--" + boundary + b"--"
        terminal = (b"\r\n" + closing, b"\r\n" + closing + b"\r\n")
        # Starlette's parser accepts some incomplete endings as partial forms.
        # Require a delimiter line before letting any parsed fields reach jobs.
        if body not in (closing, closing + b"\r\n") and not body.endswith(terminal):
            raise HTTPException(400, "invalid form")

        delivered = False

        async def replay() -> Message:
            nonlocal delivered
            if delivered:
                return {"type": "http.request", "body": b"", "more_body": False}
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}

        parsed = Request(request.scope, replay)
        try:
            async with parsed.form(
                max_files=0,
                max_fields=FORM_MAX_FIELDS,
                max_part_size=FORM_MAX_BYTES,
            ) as fields:
                values = {}
                for key, value in fields.multi_items():
                    if key in values or not isinstance(value, str):
                        raise HTTPException(400, "invalid form")
                    values[key] = value
                return values
        except HTTPException:
            raise HTTPException(400, "invalid form") from None
        except ValueError, UnicodeError:
            raise HTTPException(400, "invalid form") from None

    try:
        fields = parse_qs(
            body.decode("utf-8"),
            max_num_fields=FORM_MAX_FIELDS,
            keep_blank_values=True,
            strict_parsing=True,
            errors="strict",
        )
        if any(len(values) != 1 for values in fields.values()):
            raise ValueError("duplicate field")
        return {key: values[0] for key, values in fields.items()}
    except ValueError, UnicodeError:
        raise HTTPException(400, "invalid form") from None
