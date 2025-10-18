"""Compatibility shim: re-export models from `app.db`.

Keeping `app.db` as the canonical definition allows pytest to reset
metadata by purging that module name. This module simply forwards imports
for readability under `app.domain`.
"""

from app.db import *  # noqa: F401,F403
