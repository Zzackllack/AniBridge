from __future__ import annotations

from fastapi import APIRouter

from app.catalog import get_catalog_indexer

router = APIRouter()


@router.get("/health")
async def healthcheck():
    return {
        "status": "ok",
        "catalog": get_catalog_indexer().get_progress_snapshot(),
    }


@router.get("/health/catalog")
async def catalog_healthcheck():
    return get_catalog_indexer().get_progress_snapshot()
