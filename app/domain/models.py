"""Compatibility shim: re-export models from `app.models`.

Keeping `app.models` as the canonical definition allows pytest to reset
metadata by purging that module name. This module simply forwards imports
for readability under `app.domain`.
"""

from app.models import *  # noqa: F401,F403
