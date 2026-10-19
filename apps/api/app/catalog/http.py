"""Opt-in request API search; media resolution belongs to durable local grabs."""

import hmac
import sqlite3
import time
import xml.etree.ElementTree as ET

from fastapi import APIRouter, HTTPException, Request, Response

from . import search
from .runtime import Runtime
from catalog_core.query_client import Unavailable

router = APIRouter()


def runtime(request: Request) -> Runtime:
    service = getattr(request.app.state, "catalog", None)
    if service is None:
        raise HTTPException(503, "catalog_unavailable", headers={"Retry-After": "60"})
    return service


def xml_error(
    code: int, status: int, description: str, retry: str | None = None
) -> Response:
    return Response(
        ET.tostring(ET.Element("error", code=str(code), description=description)),
        status_code=status,
        media_type="application/xml",
        headers={"Retry-After": retry} if retry else None,
    )


def caps(anime: int, movie: int) -> bytes:
    root = ET.Element("caps")
    ET.SubElement(root, "server", title="AniBridge")
    ET.SubElement(root, "limits", default="100", max="100")
    available = ET.SubElement(root, "searching")
    ET.SubElement(available, "search", available="yes", supportedParams="q")
    ET.SubElement(
        available,
        "tv-search",
        available="yes",
        supportedParams="q,season,ep,tvdbid,tmdbid,imdbid",
    )
    ET.SubElement(
        available,
        "movie-search",
        available="yes",
        supportedParams="q,year,tmdbid,imdbid",
    )
    categories = ET.SubElement(root, "categories")
    ET.SubElement(categories, "category", id=str(anime), name="Anime")
    ET.SubElement(categories, "category", id="5000", name="TV")
    ET.SubElement(categories, "category", id=str(movie), name="Movies")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


@router.get("/torznab/api")
async def torznab(request: Request):
    from app.config import (
        CATALOG_SITE_CONFIGS,
        INDEXER_API_KEY,
        STRM_FILES_MODE,
        TORZNAB_CAT_ANIME,
        TORZNAB_CAT_MOVIE,
        TORZNAB_FAKE_SEEDERS,
        TORZNAB_FAKE_LEECHERS,
    )

    params = dict(request.query_params)
    if INDEXER_API_KEY and not hmac.compare_digest(
        params.get("apikey", "").encode(), INDEXER_API_KEY.encode()
    ):
        # Preserve the legacy HTTP auth result, without logging the supplied key.
        raise HTTPException(401, "invalid apikey")
    if any(len(request.query_params.getlist(key)) != 1 for key in params):
        return xml_error(200, 400, "Invalid request")
    if params.get("t") == "caps":
        return Response(
            caps(TORZNAB_CAT_ANIME, TORZNAB_CAT_MOVIE), media_type="application/xml"
        )
    try:
        query = search.parse(params)
    except ValueError as exc:
        unsupported = str(exc) in ("unsupported_function", "unsupported_id")
        return xml_error(
            202 if unsupported else 200,
            400,
            "Unsupported request" if unsupported else "Invalid request",
        )
    modes = {"no": ("download",), "only": ("strm",), "both": ("download", "strm")}[
        STRM_FILES_MODE
    ]
    names = {label: code for code, label in search.LANGUAGES.items()}
    names["Deutsch"] = "de-dub"
    languages = {
        provider: {
            names[name] for name in options["default_languages"] if name in names
        }
        for provider, options in CATALOG_SITE_CONFIGS.items()
    }
    try:
        service = runtime(request)
        if service.search is None:
            raise Unavailable("cache_unavailable")
        rows, total, headers = await service.search.search(
            params,
            now=int(time.time()),
            modes=modes,
            languages=languages,
            anime_category=TORZNAB_CAT_ANIME,
            movie_category=TORZNAB_CAT_MOVIE,
        )
    except (ValueError, sqlite3.Error, Unavailable, TimeoutError) as exc:
        if str(exc) == "query_too_broad":
            return xml_error(200, 400, "Query is too broad")
        return xml_error(
            900,
            503,
            "Catalog temporarily unavailable",
            "1" if str(exc) == "search_busy" else "60",
        )
    return Response(
        search.rss(
            rows,
            total,
            query.offset,
            seeders=TORZNAB_FAKE_SEEDERS,
            leechers=TORZNAB_FAKE_LEECHERS,
        ),
        media_type="application/xml",
        headers=headers,
    )
