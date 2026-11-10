"""One generated collection/export pass in a network-disabled disposable container."""

import asyncio
import json
import resource
import tempfile
import time
from pathlib import Path

from catalog_worker.config import load
from catalog_worker.pilot_seed import seed
from catalog_worker.storage import status


with tempfile.TemporaryDirectory(prefix="bounded-collector-") as temporary:
    root = Path(temporary)
    config = root / "worker.json"
    config.write_text(
        json.dumps(
            {
                "providers": {"aniworld.to": "https://fixture.invalid"},
                "canonical_sources": {"tv": "off", "movie": "off"},
                "state_dir": str(root / "state"),
                "output_dir": str(root / "read"),
                "source_id": "measured-fixture",
                "publication_sources": ["synthetic-v1"],
            }
        )
    )
    started, cpu = time.perf_counter(), time.process_time()
    result = asyncio.run(seed(config))
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    print(
        json.dumps(
            {
                "result": result,
                "duration_s": round(time.perf_counter() - started, 3),
                "collector_cpu_s": round(time.process_time() - cpu, 3),
                "child_cpu_s": round(children.ru_utime + children.ru_stime, 3),
                "collector_process_peak_rss_bytes": resource.getrusage(
                    resource.RUSAGE_SELF
                ).ru_maxrss
                * 1024,
                "largest_child_peak_rss_bytes": children.ru_maxrss * 1024,
                "container_peak_bytes": int(
                    Path("/sys/fs/cgroup/memory.peak").read_text()
                ),
                "storage": status(load(config)),
                "limits": "512-MiB/2-vCPU; network disabled; generated HTML; no provider metadata or media",
            }
        )
    )
