from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware


def apply_cors_middleware(
    app: FastAPI,
    *,
    origins: list[str],
    allow_credentials: bool,
) -> None:
    """Apply CORSMiddleware using AniBridge config semantics.

    - No middleware if origins is empty.
    - Wildcard origins ("*") always disable credentials.
    """

    if not origins:
        return

    is_wildcard = "*" in origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if is_wildcard else origins,
        allow_credentials=False if is_wildcard else allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )
