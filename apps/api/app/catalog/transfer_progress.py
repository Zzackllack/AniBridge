"""Byte accounting across selected tracks; estimates are never exact sizes."""

import math
from dataclasses import dataclass

MAX_COUNTER = 2**63 - 1


def counter(value: object) -> int | None:
    if type(value) not in (int, float):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return min(MAX_COUNTER, max(0, int(value)))


def progress_counters(values: dict, prior: int = 0) -> dict:
    """Keep the child message integral, including yt-dlp's estimated totals."""
    downloaded = counter(values.get("downloaded_bytes")) or 0
    exact = counter(values.get("total_bytes"))
    if exact is not None and exact < downloaded:
        exact = None
    estimate = counter(values.get("total_bytes_estimate"))
    total = exact or estimate
    return {
        "downloaded_bytes": min(MAX_COUNTER, prior + downloaded),
        "total_bytes": min(MAX_COUNTER, prior + max(downloaded, total))
        if total
        else None,
        "total_bytes_estimated": bool(not exact and estimate),
        "speed": counter(values.get("speed")),
        "eta": counter(values.get("eta")),
    }


@dataclass
class Track:
    downloaded: int = 0
    total: int | None = None
    estimated: bool = False


class TransferProgress:
    def __init__(self, formats: list[dict]) -> None:
        self.tracks = []
        for item in formats:
            exact = counter(item.get("filesize"))
            estimate = counter(item.get("filesize_approx"))
            self.tracks.append(
                Track(total=exact or estimate, estimated=bool(not exact and estimate))
            )

    def update(self, index: int, values: dict) -> dict:
        track = self.tracks[index]
        update = progress_counters(values)
        track.downloaded = max(track.downloaded, update["downloaded_bytes"])
        total = update["total_bytes"]
        if total is not None and (
            not update["total_bytes_estimated"]
            or track.total is None
            or track.estimated
        ):
            track.total, track.estimated = total, update["total_bytes_estimated"]
        # A changing estimate can fall behind transferred bytes. A stale exact
        # size is invalid evidence; neither case may create negative remaining.
        if track.total is not None and track.downloaded > track.total:
            track.total = track.downloaded if track.estimated else None
        return self._snapshot(index, update["speed"], update["eta"])

    def finish(self, index: int, size: int) -> dict:
        self.tracks[index] = Track(downloaded=size, total=size)
        return self._snapshot(index, 0, 0)

    def _snapshot(self, index: int, speed: int | None, eta: int | None) -> dict:
        total = (
            min(MAX_COUNTER, sum(track.total for track in self.tracks))
            if all(track.total is not None for track in self.tracks)
            else None
        )
        future = self.tracks[index + 1 :]
        if any(track.total is None for track in future):
            eta = None
        elif future:
            if speed:
                current = self.tracks[index]
                remaining = (
                    max(0, current.total - current.downloaded)
                    if current.total is not None
                    else None
                )
                eta = (
                    min(
                        MAX_COUNTER,
                        int(
                            (eta if eta is not None else remaining / speed)
                            + sum(track.total for track in future) / speed
                        ),
                    )
                    if eta is not None or remaining is not None
                    else None
                )
            else:
                eta = None
        return {
            "downloaded_bytes": min(
                MAX_COUNTER, sum(track.downloaded for track in self.tracks)
            ),
            "total_bytes": total,
            "total_bytes_estimated": total is not None
            and any(track.estimated for track in self.tracks),
            "speed": speed,
            "eta": eta,
        }
