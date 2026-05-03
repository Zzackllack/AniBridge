from __future__ import annotations


class CatalogNotReadyError(RuntimeError):
    """Raised when catalog-dependent routes are hit before bootstrap completes."""
