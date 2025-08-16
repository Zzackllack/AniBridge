"""Compatibility shim for app.utils.title_resolver.

Reloads the underlying module so environment changes (e.g., test-set paths)
take effect across tests that only purge `app.title_resolver`.
"""

import importlib
import app.utils.title_resolver as _tr

_tr = importlib.reload(_tr)

from app.utils.title_resolver import *  # noqa: F401,F403
