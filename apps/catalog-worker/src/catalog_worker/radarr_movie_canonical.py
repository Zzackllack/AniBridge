"""Keyless Radarr movie identity, using the same title/year policy as TV.

Search results are candidates, never a first-result binding. A unique exact
name/year match must survive an independent movie-detail lookup.
"""

from catalog_core.identity import validate_external_id
from catalog_core.json_codec import require

from .mapping import CanonicalTitle, match_title, search_terms

ORIGIN = "https://api.radarr.video"
PROVENANCE = "radarr-skyhook-v1"
MATCHER = "radarr-title-year-1"
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


def _candidates(response: object) -> list[tuple[CanonicalTitle, str | None, int]]:
    require(
        type(response) is list and len(response) <= MAX_CANDIDATES,
        "invalid Radarr movie candidates",
    )
    return [_movie(item) for item in response]


async def lookup(request, row, names: tuple[str, ...]):
    """Use an explicit ID when present, otherwise verify a unique title/year."""
    imdb_id = row["explicit_imdb"]
    if imdb_id:
        validate_external_id("imdb", imdb_id)
        response = await request("/v1/movie/imdb/" + imdb_id, origin=ORIGIN)
        matching = [item for item in _candidates(response) if item[1] == imdb_id]
        if len(matching) != 1:
            return None, {}
        candidate, search_imdb, movie_id = matching[0]
        evidence = "explicit_id"
    else:
        year = row["year"]
        if type(year) is not int or not 1800 <= year <= 2200:
            return None, {}
        candidates = []
        for term in search_terms(names):
            response = await request(
                "/v1/search", {"q": term, "year": str(year)}, origin=ORIGIN
            )
            candidates.extend(_candidates(response))
        matched = match_title(
            names, year, "movie", tuple(item[0] for item in candidates)
        )
        if matched is None:
            return None, {}
        candidate, evidence = matched
        movie_id = int(candidate.external_id)
        associations = {
            item[1] for item in candidates if item[2] == movie_id and item[1]
        }
        require(len(associations) <= 1, "Radarr search IMDb mismatch")
        search_imdb = next(iter(associations), None)

    details = await request("/v1/movie/" + str(movie_id), origin=ORIGIN)
    detailed, detail_imdb, detail_id = _movie(details)
    require(detail_id == movie_id, "Radarr detail TMDb ID mismatch")
    if imdb_id or search_imdb:
        require(detail_imdb == (imdb_id or search_imdb), "Radarr detail IMDb mismatch")
    if not imdb_id:
        require(
            match_title(names, row["year"], "movie", (detailed,)) is not None,
            "Radarr detail title/year mismatch",
        )
    return (detailed, evidence), {"imdb_id": detail_imdb, "id": detail_id}
