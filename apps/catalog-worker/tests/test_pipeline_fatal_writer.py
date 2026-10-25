"""An unexpected writer failure must terminate the worker, not strand producers."""

import asyncio

import pytest
from test_pipeline import collectors

from catalog_worker.collector import Ready
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
