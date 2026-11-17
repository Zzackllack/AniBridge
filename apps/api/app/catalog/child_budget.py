"""One process-wide admission budget for all private consumer subprocesses."""

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Literal

Kind = Literal["download", "validation", "sample"]


@dataclass(eq=False)
class Lease:
    owner: "ChildBudget"
    kind: Kind
    cancel: threading.Event = field(default_factory=threading.Event)

    def close(self) -> None:
        with self.owner.changed:
            self.owner.active.discard(self)
            self.owner.changed.notify_all()


class ChildBudget:
    """Each admitted child is independently limited to 256 MiB by its launcher.

    Two occupied slots represent the full 512-MiB child allowance. Optional
    sampling runs only while idle and receives cancellation when required work
    arrives; its slot remains occupied until its owner confirms termination.
    """

    def __init__(self) -> None:
        self.changed = threading.Condition()
        self.active: set[Lease] = set()

    def try_acquire(self, kind: Kind) -> Lease | None:
        if kind not in ("download", "validation", "sample"):
            raise ValueError("invalid child kind")
        with self.changed:
            if kind == "sample":
                if self.active:
                    return None
            else:
                samples = [lease for lease in self.active if lease.kind == "sample"]
                for lease in samples:
                    lease.cancel.set()
                if samples:
                    return None
            if len(self.active) >= 2:
                return None
            lease = Lease(self, kind)
            self.active.add(lease)
            return lease

    @contextmanager
    def hold(self, kind: Kind, cancel: threading.Event | None = None):
        with self.changed:
            while True:
                if cancel is not None and cancel.is_set():
                    raise InterruptedError("child admission cancelled")
                lease = self.try_acquire(kind)
                if lease is not None:
                    break
                self.changed.wait(timeout=0.1)
        try:
            yield lease
        finally:
            lease.close()


CONSUMER_CHILDREN = ChildBudget()
