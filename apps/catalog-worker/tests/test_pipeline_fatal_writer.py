"""An unexpected writer failure must terminate the worker, not strand producers."""

import asyncio
import gc

import pytest
from test_pipeline import collectors

from catalog_worker.collector import Ready
from catalog_worker.cli import _cancel_and_wait
from catalog_worker.pipeline import Pipeline


@pytest.mark.parametrize("once", [False, True])
def test_fatal_writer_failure_propagates_and_settles_producer_cleanup(tmp_path, once):
    group = collectors(tmp_path)

    async def collected(plan):
        return Ready(plan, None, "admission_deferred", 1)

    def broken(ready):
        raise RuntimeError("injected fatal writer")

    for collector in group:
        collector.collect = collected
    group[0].apply = broken
    pipeline = Pipeline(group, lambda *args: None)

    async def run():
        with pytest.raises(RuntimeError, match="fatal writer"):
            await asyncio.wait_for(pipeline.run(once=once), 1)
        assert all(count == 0 for count in pipeline.busy.values())
        assert not [
            t
            for t in asyncio.all_tasks()
            if t is not asyncio.current_task() and not t.done()
        ]

    try:
        asyncio.run(run())
    finally:
        for collector in group:
            collector.state.close()


def test_parent_cancellation_waits_for_pipeline_shutdown_without_orphans(tmp_path):
    group = collectors(tmp_path)
    pipeline = Pipeline(group, lambda *args: None)
    no_progress = asyncio.Event()
    warnings = []

    async def page(_collector):
        no_progress.set()
        return False

    pipeline.page = page

    async def maintain():
        await asyncio.Event().wait()

    tasks = []

    async def supervise():
        try:
            await asyncio.gather(*tasks)
        finally:
            await _cancel_and_wait(tasks)

    async def scenario():
        loop = asyncio.get_running_loop()
        previous_handler = loop.get_exception_handler()
        loop.set_exception_handler(lambda _loop, context: warnings.append(context))
        try:
            tasks.extend(
                [
                    asyncio.create_task(pipeline.run()),
                    asyncio.create_task(maintain()),
                ]
            )
            parent = asyncio.create_task(supervise())
            await no_progress.wait()
            # This is the collect task cancellation requested by its SIGTERM
            # handler while producers are in their no-progress sleep.
            parent.cancel()
            with pytest.raises(asyncio.CancelledError):
                await parent

            await asyncio.sleep(0)
            gc.collect()
            assert all(value == 0 for value in pipeline.busy.values())
            assert not [
                task
                for task in asyncio.all_tasks()
                if task is not asyncio.current_task() and not task.done()
            ]
            assert not any(
                context.get("message")
                == "_GatheringFuture exception was never retrieved"
                for context in warnings
            )
        finally:
            loop.set_exception_handler(previous_handler)

    try:
        asyncio.run(scenario())
    finally:
        for collector in group:
            collector.state.close()
