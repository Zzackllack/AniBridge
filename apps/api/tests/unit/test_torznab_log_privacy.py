"""Rejected legacy requests must not disclose credentials or search inputs."""

import pytest
from fastapi import HTTPException
from loguru import logger

from app.api.torznab import api, utils


@pytest.mark.parametrize("operation", ["search", "private-operation-value"])
def test_rejected_request_keeps_inputs_out_of_logs(monkeypatch, operation):
    monkeypatch.setattr(utils, "INDEXER_API_KEY", "expected-private-key")
    messages = []
    sink = logger.add(lambda message: messages.append(message.record["message"]))
    try:
        with pytest.raises(HTTPException) as error:
            api.torznab_api(
                request=None,
                t=operation,
                apikey="supplied-private-key",
                q="private-search-title",
                session=None,
            )
        assert error.value.status_code == 401
    finally:
        logger.remove(sink)
    assert messages == [
        "Torznab request: operation="
        + ("search" if operation == "search" else "unsupported"),
        "API key missing or invalid",
    ]
