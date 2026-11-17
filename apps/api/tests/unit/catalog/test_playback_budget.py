"""Playback resolution shares the process-wide child budget."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.catalog import strm_http
from app.catalog.child_budget import ChildBudget
from app.catalog.strm_http import Playback
from test_jobs import setup_jobs


def test_resolution_refuses_a_third_supervised_child(tmp_path, monkeypatch):
    jobs = setup_jobs(tmp_path)
    budget = ChildBudget()
    monkeypatch.setattr(strm_http, "CONSUMER_CHILDREN", budget)
    playback = Playback(
        SimpleNamespace(directory=tmp_path),
        jobs,
        {"aniworld.to": "https://provider.invalid"},
        (),
    )
    first = budget.try_acquire("download")
    second = budget.try_acquire("download")
    assert first is not None and second is not None
    try:
        with pytest.raises(HTTPException) as error:
            asyncio.run(playback.resolve({"provider": "aniworld.to"}))
        assert error.value.status_code == 503
        assert error.value.headers == {"Retry-After": "60"}
    finally:
        first.close()
        second.close()
    assert not budget.active
