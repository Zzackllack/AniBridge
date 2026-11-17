"""Request-frame and deadline bounds for qBittorrent form input."""

import asyncio

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.catalog import qbit_forms


def _form_request(receive):
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v2/torrents/add",
            "headers": [(b"content-type", b"application/x-www-form-urlencoded")],
        },
        receive,
    )


def test_form_rejects_excessive_empty_asgi_request_frames():
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": True}

    with pytest.raises(HTTPException) as error:
        asyncio.run(qbit_forms.form(_form_request(receive)))
    assert error.value.status_code == 400


def test_form_times_out_while_waiting_for_body(monkeypatch):
    monkeypatch.setattr(qbit_forms, "FORM_DEADLINE_S", 0.01)

    async def receive():
        await asyncio.sleep(0.05)
        return {"type": "http.request", "body": b"urls=fixture", "more_body": False}

    with pytest.raises(HTTPException) as error:
        asyncio.run(qbit_forms.form(_form_request(receive)))
    assert error.value.status_code == 408
