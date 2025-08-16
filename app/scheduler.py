"""Compatibility shim for app.core.scheduler.

Reloads the underlying module to obtain a fresh executor/RUNNING state when
tests reload only `app.main` but not `app.scheduler`.
"""

import importlib
import app.core.scheduler as _core_scheduler

_core_scheduler = importlib.reload(_core_scheduler)

from app.core.scheduler import *  # noqa: F401,F403
