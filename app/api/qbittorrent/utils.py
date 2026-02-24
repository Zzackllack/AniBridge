from __future__ import annotations

from datetime import datetime, timezone


def _to_utc_timestamp(dt: datetime) -> int:
    """Convert a datetime to a UTC POSIX timestamp integer.

    Naive datetimes are treated as UTC by assigning `timezone.utc`. Aware
    datetimes are converted to UTC via `astimezone(timezone.utc)`.

    Returns:
        int: POSIX timestamp in whole seconds.

    Raises:
        TypeError: If `dt` is `None` or not a datetime instance.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return int(dt.timestamp())
