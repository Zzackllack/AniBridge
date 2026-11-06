"""Subprocess supervision tests, separate from provider or media import proof."""

import asyncio
import sys

import pytest
from app.catalog.executor import SubprocessExecutor


@pytest.mark.skipif(sys.platform != "linux", reason="Linux child enforcement")
def test_cancellation_reaps_transfer_process(tmp_path):
    executor = SubprocessExecutor({}, (), tmp_path)

    async def scenario():
        started = asyncio.get_running_loop().time()
        task = asyncio.create_task(
            executor._run(
                "timeit", ["-n", "1", "-r", "1", "import time; time.sleep(60)"]
            )
        )
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert asyncio.get_running_loop().time() - started < 2

    asyncio.run(scenario())


@pytest.mark.skipif(sys.platform != "linux", reason="Linux child enforcement")
def test_deadline_stops_stalled_child(tmp_path):
    executor = SubprocessExecutor({}, (), tmp_path)

    async def scenario():
        started = asyncio.get_running_loop().time()
        with pytest.raises(TimeoutError):
            await executor._run(
                "timeit",
                ["-n", "1", "-r", "1", "import time; time.sleep(60)"],
                deadline=0.1,
            )
        assert asyncio.get_running_loop().time() - started < 2

    asyncio.run(scenario())


@pytest.mark.skipif(sys.platform != "linux", reason="Linux child enforcement")
def test_execution_rechecks_save_path_after_admission(tmp_path):
    download = tmp_path / "downloads"
    download.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = download / "changed"
    link.symlink_to(outside, target_is_directory=True)
    executor = SubprocessExecutor(
        {"aniworld.to": "https://example.invalid"}, ("VOE",), download
    )
    payload = {"provider": "aniworld.to", "mode": "download", "save_path": str(link)}
    result = asyncio.run(executor(payload, lambda update: None))
    assert result.code == "invalid_output_path"
    assert not list(outside.iterdir())


@pytest.mark.skipif(sys.platform != "linux", reason="Linux child enforcement")
def test_installed_parser_and_transfer_import_within_child_address_limit(tmp_path):
    # This formerly failed with RuntimeError from the upstream pool's thread
    # startup. No provider request is needed to reproduce the address exhaustion.
    script = "\n".join(
        [
            "import logging, os, resource",
            "from catalog_core.supervisor import limit_child",
            "limit_child(output_bytes=resource.RLIM_INFINITY)",
            "logging.disable(logging.CRITICAL)",
            "from loguru import logger",
            "logger.remove(); logger.disable('')",
            f"os.environ['ANIWORLD_INSTALL_FOLDER'] = {str(tmp_path / 'upstream')!r}",
            "from app.catalog.aniworld_resolution import resolve",
            "from app.catalog.media_download import transfer",
            "from app.catalog.resolution_transport import Budget",
            "budget = Budget()",
            "from app.utils.aniworld_compat import prepare_aniworld_home",
            "prepare_aniworld_home()",
            "from aniworld.extractors.provider.voe import extract_voe_source_from_html",
            "assert resource.getrlimit(resource.RLIMIT_AS)[0] == 256 * 1024**2",
            "budget.close()",
        ]
    )
    executor = SubprocessExecutor({}, (), tmp_path)
    assert (
        asyncio.run(
            executor._run("timeit", ["-n", "1", "-r", "1", script], deadline=20)
        )
        == 0
    )


@pytest.mark.skipif(sys.platform != "linux", reason="Linux child enforcement")
@pytest.mark.parametrize("channel", ["stdout", "stderr"])
def test_child_output_overflow_fails_even_when_child_exits_successfully(
    tmp_path, channel
):
    executor = SubprocessExecutor({}, (), tmp_path)
    code = asyncio.run(
        executor._run(
            "timeit",
            ["-n", "1", "-r", "1", f"import sys; sys.{channel}.write('x' * 70000)"],
            deadline=5,
        )
    )
    assert code != 0
