"""Runtime wiring for durable scheduling, without starting the service."""

import asyncio

import pytest

from app.catalog import runtime as runtime_module
from app.catalog.config import Config
from test_jobs import setup_jobs


def _config() -> Config:
    return Config(
        mode="query",
        origin="https://catalog.example",
        source_id="source",
        api_token="x" * 16,
    )


@pytest.mark.parametrize(
    ("configured", "expected"),
    [(1, 1), (2, 2), (3, 2), (8, 2)],
)
def test_runtime_uses_global_concurrency_within_child_budget(
    tmp_path, monkeypatch, configured, expected
):
    jobs = setup_jobs(tmp_path)
    created = {}

    class CapturingExecutor:
        def __init__(
            self,
            origins,
            hosts,
            download_root,
            *,
            bandwidth=None,
            strm_mode="direct",
        ) -> None:
            created["bandwidth"] = bandwidth
            created["executor"] = self

    monkeypatch.setattr(runtime_module, "SubprocessExecutor", CapturingExecutor)
    monkeypatch.setattr(runtime_module.sys, "platform", "linux")
    monkeypatch.setattr(runtime_module, "MAX_CONCURRENCY", configured)
    monkeypatch.setattr(
        runtime_module, "DOWNLOAD_RATE_LIMIT_BYTES_PER_SEC", 4 * 1024**2
    )
    service = runtime_module.Runtime(
        _config(),
        jobs.filename,
        tmp_path / "catalog",
        jobs.download_dir,
        {"aniworld.to": "https://aniworld.example"},
        ("VOE",),
    )
    try:
        assert service.runner.concurrency == expected
        assert created["bandwidth"] == 4 * 1024**2
        assert service.runner.execute is created["executor"]
    finally:
        _close(service)


def test_runtime_preserves_injected_executor_and_explicit_concurrency(
    tmp_path, monkeypatch
):
    jobs = setup_jobs(tmp_path)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("injected executor must not be replaced")

    monkeypatch.setattr(runtime_module, "SubprocessExecutor", forbidden)
    executor = object()
    service = runtime_module.Runtime(
        _config(),
        jobs.filename,
        tmp_path / "catalog",
        jobs.download_dir,
        {"aniworld.to": "https://aniworld.example"},
        ("VOE",),
        executor=executor,
        concurrency=1,
        bandwidth=0,
    )
    try:
        assert service.runner.execute is executor
        assert service.runner.concurrency == 1
        assert service.runner.progress_log is not None
    finally:
        _close(service)


def _close(service) -> None:
    asyncio.run(service.playback.close())
    asyncio.run(service.metadata.close())
    service.owner.close()
