import os
import subprocess
import threading
import time

import pytest

from catalog_core import supervisor


def test_cancellation_kills_and_reaps_child(monkeypatch):
    original = subprocess.Popen
    launched = []

    def launch(*args, **kwargs):
        process = original(*args, **kwargs)
        launched.append(process)
        return process

    monkeypatch.setattr(supervisor.subprocess, "Popen", launch)
    cancel = threading.Event()
    timer = threading.Timer(0.1, cancel.set)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(InterruptedError):
            supervisor.run_child(
                "timeit",
                ["-n", "1", "-r", "1", "import time; time.sleep(60)"],
                60,
                cancel=cancel,
            )
    finally:
        timer.join()
    assert time.monotonic() - started < 2
    assert launched[0].poll() is not None
    with pytest.raises(ProcessLookupError):
        os.kill(launched[0].pid, 0)
