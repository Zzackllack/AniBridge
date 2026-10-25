"""Durability primitives shared by publication and local activation."""

import os
from pathlib import Path
from uuid import uuid4


def fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


class ProcessLock:
    """Reject multiple owners before touching private state or orphan files."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.file = path.open("a+b")
        try:
            if os.name == "nt":
                import msvcrt

                self.file.seek(0)
                if not self.file.read(1):
                    self.file.write(b"\0")
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Some shared filesystems accept flock without excluding another
                # open handle (observed with Docker Desktop's Mac bind mounts).
                # Refuse ownership rather than allow concurrent state writers.
                with path.open("a+b") as probe:
                    try:
                        fcntl.flock(probe.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        pass
                    else:
                        fcntl.flock(probe.fileno(), fcntl.LOCK_UN)
                        raise RuntimeError("data volume does not enforce process locks")
        except OSError:
            self.file.close()
            raise RuntimeError("data volume already owned by another process") from None
        except BaseException:
            self.file.close()
            raise

    def close(self) -> None:
        self.file.close()
