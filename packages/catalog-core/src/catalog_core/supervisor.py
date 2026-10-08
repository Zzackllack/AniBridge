"""Hard deadlines for untrusted parsing and validation, independent of threads."""

import os
import signal
import subprocess
import sys
import threading
import time

from .json_codec import ContractError


def limit_child(
    memory_bytes: int = 256 * 1024**2, output_bytes: int = 64 * 1024**2
) -> None:
    """Set limits before processing an untrusted input in a fresh interpreter."""
    if sys.platform == "win32":
        # No unbounded substitute: a Windows Job Object implementation is a
        # packaging gate before this feature can run in a Windows executable.
        raise RuntimeError("bounded catalog subprocesses require POSIX")
    import resource

    if sys.platform == "linux":
        import ctypes

        # Session isolation lets the supervisor stop descendants. Parent-death
        # signalling also stops a child when the supervisor itself is SIGKILLed.
        expected_parent = int(os.environ.get("ANIBRIDGE_SUPERVISOR_PID", os.getppid()))
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
            raise OSError(ctypes.get_errno(), "cannot set parent-death signal")
        if os.getppid() != expected_parent:
            os.kill(os.getpid(), signal.SIGKILL)
    resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
    resource.setrlimit(resource.RLIMIT_FSIZE, (output_bytes, output_bytes))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def run_child(
    module: str,
    arguments: list[str],
    timeout: float,
    cancel: threading.Event | None = None,
) -> None:
    process = subprocess.Popen(
        [sys.executable, "-m", module, *arguments],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name != "nt",
        env={**os.environ, "ANIBRIDGE_SUPERVISOR_PID": str(os.getpid())},
    )
    try:
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if cancel is not None and cancel.is_set():
                raise InterruptedError("bounded child cancelled")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("bounded child deadline")
            try:
                process.wait(timeout=min(0.1, remaining))
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise ContractError("bounded child rejected input")
    except BaseException:
        if process.poll() is None:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.wait(timeout=2)
        raise


async def run_child_async(module: str, arguments: list[str], timeout: float) -> None:
    # Parser children use limit_child only; avoid importing the async runtime there.
    import asyncio

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        module,
        *arguments,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name != "nt",
        env={**os.environ, "ANIBRIDGE_SUPERVISOR_PID": str(os.getpid())},
    )
    try:
        async with asyncio.timeout(timeout):
            code = await process.wait()
        if code:
            raise ContractError("bounded child rejected input")
    finally:
        if process.returncode is None:
            if os.name != "nt":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            await asyncio.wait_for(asyncio.shield(process.wait()), 2)
