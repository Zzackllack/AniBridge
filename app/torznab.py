"""Module alias shim to app.api.torznab.

Replaces this module object with the real router module so monkeypatching
private helpers like `_slug_from_query` affects the executed code paths.
"""

import sys
import importlib
import app.api.torznab as _tn

_tn = importlib.reload(_tn)

# Replace this module with the underlying one
sys.modules[__name__] = _tn
