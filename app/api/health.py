from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def healthcheck():
    return {"status": "ok"}

