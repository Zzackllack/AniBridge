"""Keep compact secondary IDs from the same validated canonical detail record."""

from catalog_core.identity import validate_external_id
from catalog_core.json_codec import require


def identifiers(candidate, details: dict, movie: bool) -> dict[str, str]:
    result = {candidate.namespace: candidate.external_id}
    fields = (
        (("imdb", "imdb_id"),)
        if movie
        else (
            ("imdb", "imdbId"),
            ("tmdb-tv", "tmdbId"),
        )
    )
    for namespace, field in fields:
        value = details.get(field)
        require(type(value) is not bool, "invalid canonical secondary ID")
        if value in (None, "", 0):
            continue
        if namespace == "imdb":
            require(type(value) is str, "invalid canonical secondary ID")
        else:
            require(type(value) is int and value > 0, "invalid canonical secondary ID")
            value = str(value)
        validate_external_id(namespace, value)
        result[namespace] = value
    return result
