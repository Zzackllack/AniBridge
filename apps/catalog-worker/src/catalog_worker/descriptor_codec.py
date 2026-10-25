"""Validate stored compact evidence before any cross-provider reuse."""

import hashlib
import json

from catalog_core.json_codec import require

from .canonical_ids import identifiers
from .mapping import CanonicalEpisode, CanonicalTitle
from .parent_evidence import valid as valid_parent

LIMIT = 8 * 1024**2


def decode(
    raw: str, digest: str, external: str, codec: int
) -> tuple[dict, list[CanonicalEpisode]]:
    require(isinstance(raw, str) and len(raw) <= LIMIT, "descriptor limit")
    encoded = raw.encode()
    require(len(encoded) <= LIMIT, "descriptor limit")
    # This detects accidental mutation; a hash stored beside its payload is
    # not an authenticity proof against a writer controlling the private DB.
    require(hashlib.sha256(encoded).hexdigest() == digest, "descriptor digest")
    data = json.loads(raw)
    require(isinstance(data, dict), "descriptor object")
    require(
        type(data.get("codec")) is int and data["codec"] == codec, "descriptor codec"
    )
    require(
        type(data.get("tvdbId")) is int and str(data["tvdbId"]) == external,
        "descriptor parent",
    )
    require(valid_parent(data.get("parent")), "descriptor proof")
    require(data.get("api") in ("skyhook-v1", "skyhook-v2"), "descriptor API")
    identifiers(CanonicalTitle("tvdb", external, (), None, "series"), data, False)
    for key in ("languages", "missing_languages"):
        values = data.get(key)
        require(
            isinstance(values, list)
            and len(values) <= 100
            and all(
                isinstance(v, str)
                and len(v) == 3
                and v.isascii()
                and v.islower()
                and v.isalpha()
                for v in values
            ),
            "descriptor languages",
        )
    rows = data.get("episodes")
    require(isinstance(rows, list) and len(rows) <= 100000, "descriptor episodes")
    records, coordinates, identities = [], set(), set()
    for row in rows:
        require(isinstance(row, dict), "descriptor episode")
        season, number = row.get("season"), row.get("episode")
        name, eid, aliases = (
            row.get("title"),
            row.get("external_id"),
            row.get("aliases"),
        )
        require(
            type(season) is int
            and 0 <= season <= 2**31 - 1
            and type(number) is int
            and 1 <= number <= 2**31 - 1,
            "descriptor coordinate",
        )
        require(isinstance(name, str) and len(name.encode()) <= 512, "descriptor name")
        require(
            eid is None
            or isinstance(eid, str)
            and 1 <= len(eid) <= 20
            and eid.isascii()
            and eid.isdecimal()
            and int(eid) > 0,
            "descriptor identity",
        )
        require(
            isinstance(aliases, list)
            and len(aliases) <= 100
            and all(isinstance(a, str) and len(a.encode()) <= 512 for a in aliases),
            "descriptor aliases",
        )
        require(
            (season, number) not in coordinates
            and (eid is None or eid not in identities),
            "descriptor conflict",
        )
        coordinates.add((season, number))
        if eid is not None:
            identities.add(eid)
        records.append(CanonicalEpisode(season, number, name, eid, tuple(aliases)))
    return data, records
