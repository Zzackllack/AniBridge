"""Module alias shim to app.api.qbittorrent.

Replaces this module object with the real router module so monkeypatching
attributes like `schedule_download` affects the executed code paths.
"""

import sys
import importlib
import app.api.qbittorrent as _qb

_qb = importlib.reload(_qb)

sys.modules[__name__] = _qb
