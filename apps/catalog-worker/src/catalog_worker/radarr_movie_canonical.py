"""Keyless Radarr SkyHook movie identity using explicit IMDb IDs only.

The SkyHook search endpoint returns a bare, potentially capped list. Without a
completeness signal it cannot prove title/year uniqueness, so this adapter
does not use it for canonical matching.
"""

from catalog_core.identity import validate_external_id
from catalog_core.json_codec import require

from .mapping import CanonicalTitle

ORIGIN = "https://api.radarr.video"
PROVENANCE = "radarr-skyhook-v1"
MAX_CANDIDATES = 1000
MAX_ALIASES = 256
MAX_TITLE_BYTES = 512


def _title_values(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    require(type(value) is list and len(value) <= MAX_ALIASES, f"invalid {field}")
    result = []
    for item in value:
        title = item.get("Title") if type(item) is dict else item
        if title is None:
            continue
        require(
            type(title) is str and len(title.encode()) <= MAX_TITLE_BYTES,
            f"invalid {field} title",
        )
        # Radarr maps optional translation/alternative-title rows directly;
        # those rows can carry an empty Title and are not usable aliases.
        if not title:
            continue
        result.append(title)
    return tuple(result)


def _movie(item: object) -> tuple[CanonicalTitle, str | None, int]:
    require(type(item) is dict, "invalid Radarr movie")
    movie_id = item.get("TmdbId")
    require(type(movie_id) is int and movie_id > 0, "invalid Radarr TMDb ID")
    imdb_id = item.get("ImdbId")
    require(imdb_id is None or type(imdb_id) is str, "invalid Radarr IMDb ID")
    if imdb_id:
        validate_external_id("imdb", imdb_id)
    year = item.get("Year")
    require(
        year is None or type(year) is int and 1800 <= year <= 2200,
        "invalid Radarr movie year",
    )

    names = []
    for field in ("Title", "OriginalTitle"):
        value = item.get(field)
        if value is None:
            continue
        require(
            type(value) is str and 0 < len(value.encode()) <= MAX_TITLE_BYTES,
            f"invalid Radarr {field}",
        )
        names.append(value)
    names.extend(_title_values(item.get("AlternativeTitles"), "alternative titles"))
    names.extend(_title_values(item.get("Translations"), "translations"))
    names = tuple(dict.fromkeys(names))
    require(bool(names), "missing Radarr movie title")
    return (
        CanonicalTitle("tmdb-movie", str(movie_id), names, year, "movie"),
        imdb_id,
        movie_id,
    )


async def lookup(request, row, names: tuple[str, ...]):
    """Resolve only a validated explicit IMDb ID, then verify movie detail.

    ``names`` and provider year are deliberately insufficient to query this
    non-paginated search API. Callers with no IMDb ID remain unresolved.
    """
    imdb_id = row["explicit_imdb"]
    if not imdb_id:
        return None, {}
    validate_external_id("imdb", imdb_id)

    response = await request(
        "/v1/movie/imdb/" + imdb_id,
        origin=ORIGIN,
    )
    require(
        type(response) is list and len(response) <= MAX_CANDIDATES,
        "invalid Radarr IMDb lookup",
    )
    candidates = [_movie(item) for item in response]
    matching = [candidate for candidate in candidates if candidate[1] == imdb_id]
    # A direct ID route is evidence only when it yields one exact association.
    if len(matching) != 1:
        return None, {}
    _candidate, _, movie_id = matching[0]

    details = await request("/v1/movie/" + str(movie_id), origin=ORIGIN)
    detailed, detail_imdb, detail_id = _movie(details)
    require(detail_id == movie_id, "Radarr detail TMDb ID mismatch")
    require(detail_imdb == imdb_id, "Radarr detail IMDb mismatch")
    return (detailed, "explicit_id"), {"imdb_id": detail_imdb, "id": detail_id}
