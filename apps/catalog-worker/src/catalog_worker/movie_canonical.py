"""Bounded TMDb movie matching; TV results never supply a movie identity."""

from catalog_core.json_codec import require

from .mapping import CanonicalTitle, match_title

ORIGIN = "https://api.themoviedb.org"


def titles(items: object) -> tuple[CanonicalTitle, ...]:
    require(type(items) is list and len(items) <= 1000, "invalid movie candidates")
    result = []
    for item in items:
        require(type(item) is dict, "invalid movie candidate")
        movie_id = item.get("id")
        names = [item.get("title"), item.get("original_title")]
        require(type(movie_id) is int and movie_id > 0, "invalid movie ID")
        names = tuple(
            dict.fromkeys(
                name
                for name in names
                if type(name) is str and 0 < len(name.encode()) <= 512
            )
        )
        require(bool(names), "missing movie title")
        date = item.get("release_date") or ""
        require(type(date) is str, "invalid movie date")
        year = int(date[:4]) if len(date) >= 4 and date[:4].isdecimal() else None
        require(year is None or 1800 <= year <= 2200, "invalid movie year")
        result.append(CanonicalTitle("tmdb-movie", str(movie_id), names, year, "movie"))
    return tuple(result)


async def lookup(request, row, names: tuple[str, ...], token: str):
    async def get(path, params=None):
        return await request(path, params, origin=ORIGIN, bearer=token)

    if row["explicit_imdb"]:
        response = await get(
            "/3/find/" + row["explicit_imdb"], {"external_source": "imdb_id"}
        )
        require(type(response) is dict, "invalid movie find response")
        candidates = titles(response.get("movie_results"))
        matched = (candidates[0], "explicit_id") if len(candidates) == 1 else None
    elif row["year"] is not None:
        candidates = []
        for name in names[:2]:
            response = await get(
                "/3/search/movie", {"query": name, "year": str(row["year"])}
            )
            require(type(response) is dict, "invalid movie search response")
            # A truncated result set cannot prove that an exact match is unique.
            require(
                type(response.get("total_pages")) is int
                and 0 <= response["total_pages"] <= 1,
                "incomplete movie candidates",
            )
            candidates.extend(titles(response.get("results")))
        matched = match_title(names, row["year"], "movie", tuple(candidates))
    else:
        return None, {}
    if matched is None:
        return None, {}
    candidate, _ = matched
    details = await get("/3/movie/" + candidate.external_id)
    require(
        type(details) is dict
        and type(details.get("id")) is int
        and str(details["id"]) == candidate.external_id,
        "canonical movie ID mismatch",
    )
    # Detail identity/type is validated independently from the search response.
    detailed = titles([details])[0]
    require(
        detailed.external_id == candidate.external_id,
        "invalid movie details",
    )
    if row["explicit_imdb"]:
        require(
            details.get("imdb_id") == row["explicit_imdb"], "canonical IMDb mismatch"
        )
    else:
        # A detail correction cannot contradict the title/year used to bind a
        # search result. Explicit IMDb bindings use the stronger ID check above.
        confirmed = match_title(names, row["year"], "movie", (detailed,))
        require(confirmed is not None, "canonical movie title/year mismatch")
    return matched, details
