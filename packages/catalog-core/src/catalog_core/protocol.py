"""Finite metadata wire model. Jobs, URLs and local quality are excluded."""

import hashlib
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from catalog_core import identity, magnet
from catalog_core.json_codec import dumps
from catalog_core.query import parse

MAX_RESPONSE = 2 * 1024**2
PARAMS = {
    "t",
    "q",
    "tvdbid",
    "tmdbid",
    "imdbid",
    "season",
    "ep",
    "year",
    "limit",
    "offset",
    "maxage",
    "cat",
}


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Request(Model):
    operation: Literal["titles", "native", "recent"]
    provider: Literal["aniworld.to", "s.to", "megakino"] = "aniworld.to"
    params: dict[str, str] = Field(default_factory=dict)
    title_ids: list[str] = Field(default_factory=list, max_length=200)
    limit: int = Field(default=500, ge=1, le=500)
    offset: int = Field(default=0, ge=0, le=10000)
    # Requested canonical coordinates select a superset; local overrides still
    # win. Include their entity IDs even when the published map is elsewhere.
    coordinate_namespace: Literal["tvdb", "tmdb-tv"] = "tvdb"
    season: int | None = Field(default=None, ge=0, le=2**31 - 1)
    episode: int | None = Field(default=None, ge=1, le=2**31 - 1)
    include_entities: list[str] = Field(default_factory=list, max_length=1000)
    languages: list[Literal["de-dub", "en-dub", "de-sub", "en-sub"]] = Field(
        default_factory=lambda: sorted(identity.LANGUAGES), max_length=4
    )

    @model_validator(mode="after")
    def bounded(self) -> Self:
        if self.params.keys() - PARAMS:
            raise ValueError("unsupported parameters")
        query = parse(self.params)
        if len(set(self.title_ids)) != len(self.title_ids):
            raise ValueError("duplicate title IDs")
        if self.operation != "native" and (
            self.season is not None or self.episode is not None or self.include_entities
        ):
            raise ValueError("target selection requires native operation")
        if self.episode is not None and self.season is None:
            raise ValueError("episode requires season")
        for value in [*self.title_ids, *self.include_entities]:
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("invalid title ID")
        if self.operation == "native" and (not self.title_ids or not query.recent):
            raise ValueError("native requires stable title IDs only")
        if self.operation == "titles" and (query.recent or self.title_ids):
            raise ValueError("title discovery requires text or IDs")
        if self.operation == "recent" and (
            not query.recent or self.title_ids or self.limit > 100
        ):
            raise ValueError("invalid recent page")
        return self


class TitleMap(Model):
    mapping_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    title_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    namespace: Literal["tvdb", "tmdb-tv", "tmdb-movie", "imdb"]
    external_id: str = Field(max_length=128)
    source: str = Field(max_length=64)
    evidence: Literal["explicit_id", "exact_title_year", "reviewed"]
    checked_at: int = Field(ge=0)


class EpisodeMap(Model):
    mapping_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    entity_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    season: int = Field(ge=0, le=2**31 - 1)
    episode: int = Field(ge=1, le=2**31 - 1)
    external_episode_id: str | None = Field(max_length=128)
    evidence: Literal["explicit_id", "exact_title", "reviewed"]
    checked_at: int = Field(ge=0)


class Title(Model):
    provider: Literal["aniworld.to", "s.to", "megakino"] = "aniworld.to"
    title_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity_anchor: str = Field(max_length=1024)
    slug: str = Field(max_length=256)
    display_title: str = Field(max_length=512)
    search_key: str = Field(max_length=512)
    media_type: Literal["series", "movie", "unknown"]
    year: int | None = Field(ge=1800, le=2200)
    path: str = Field(max_length=1024)
    observed_at: int = Field(ge=0)
    detail_status: Literal["pending", "partial", "complete", "stale"]
    aliases: list[str] = Field(default_factory=list, max_length=32)
    mappings: list[TitleMap] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def identities(self) -> Self:
        if identity.title_id(self.provider, self.identity_anchor) != self.title_id:
            raise ValueError("title identity mismatch")
        if (
            identity.path(self.path) != self.path
            or identity.search_key(self.display_title) != self.search_key
        ):
            raise ValueError("invalid title metadata")
        for item in self.mappings:
            identity.validate_external_id(item.namespace, item.external_id)
            if item.title_id != self.title_id or item.mapping_id != identity.mapping_id(
                self.provider, self.title_id, item.namespace, item.external_id
            ):
                raise ValueError("mapping identity mismatch")
        return self


class Row(Model):
    provider: Literal["aniworld.to", "s.to", "megakino"]
    title_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    entity_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    title_anchor: str = Field(max_length=1024)
    entity_anchor: str = Field(max_length=1024)
    path: str = Field(max_length=1024)
    slug: str = Field(max_length=256)
    display_title: str = Field(max_length=512)
    year: int | None = Field(ge=1800, le=2200)
    kind: Literal["episode", "movie"]
    language: Literal["de-dub", "en-dub", "de-sub", "en-sub"]
    native_season: int | None = Field(ge=0, le=2**31 - 1)
    native_episode: int | None = Field(ge=1, le=2**31 - 1)
    namespace: str | None = Field(max_length=16)
    external_id: str | None = Field(max_length=128)
    season: int | None = Field(ge=0, le=2**31 - 1)
    episode: int | None = Field(ge=1, le=2**31 - 1)
    first_seen_at: int = Field(ge=0)
    observed_at: int = Field(ge=0)

    mappings: list[EpisodeMap] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def identities(self) -> Self:
        record = self.model_dump()
        canonical = None
        if self.namespace is not None:
            identity.validate_external_id(self.namespace, self.external_id)
            if self.kind == "movie" or self.season is not None:
                canonical = {
                    key: record[key]
                    for key in ("namespace", "external_id", "season", "episode")
                }
        elif (
            self.external_id is not None
            or self.season is not None
            or self.episode is not None
        ):
            raise ValueError("incomplete canonical map")
        if (self.season is None) != (self.episode is None):
            raise ValueError("incomplete episode map")
        magnet.validate(
            {
                **{
                    key: record[key]
                    for key in magnet.PAYLOAD_FIELDS - {"mode", "canonical"}
                },
                "mode": "download",
                "canonical": canonical,
            }
        )
        if self.first_seen_at > self.observed_at:
            raise ValueError("discovery after observation")
        return self


def request_digest(request: Request) -> str:
    return hashlib.sha256(dumps(request.model_dump())).hexdigest()


class Response(Model):
    version: Literal[1] = 1
    query_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_id: str = Field(pattern=r"^[a-z0-9._-]{1,64}$")
    provider: Literal["aniworld.to", "s.to", "megakino"]
    revision: int = Field(ge=1)
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    listing_checked_at: int = Field(ge=0)
    total: int = Field(ge=0, le=8000000)
    offset: int = Field(ge=0, le=10000)
    mapping: Literal["resolved", "partial", "unresolved"]
    rows: list[Row] = Field(max_length=500)
    titles: list[Title] = Field(default_factory=list, max_length=200)

    def check_request(self, request: Request, source_id: str) -> None:
        if self.query_digest != request_digest(request):
            raise ValueError("response query mismatch")
        if (
            self.source_id != source_id
            or self.provider != request.provider
            or self.offset != request.offset
        ):
            raise ValueError("response context mismatch")
        if request.operation == "titles":
            if self.rows or self.total != len(self.titles):
                raise ValueError("invalid candidates")
        elif len(self.rows) != min(request.limit, max(0, self.total - self.offset)):
            raise ValueError("response page mismatch")
        if any(title.provider != self.provider for title in self.titles):
            raise ValueError("title provider mismatch")
        titles = {title.title_id: title for title in self.titles}
        if len(titles) != len(self.titles):
            raise ValueError("duplicate titles")
        seen = set()
        for row in self.rows:
            if (
                row.provider != self.provider
                or row.snapshot_digest != self.snapshot_digest
                or row.release_id in seen
            ):
                raise ValueError("response identity mismatch")
            seen.add(row.release_id)
            if row.title_id not in titles:
                raise ValueError("missing title")
            title = titles[row.title_id]
            if (row.title_anchor, row.slug, row.display_title, row.year) != (
                title.identity_anchor,
                title.slug,
                title.display_title,
                title.year,
            ):
                raise ValueError("row/title mismatch")
            if request.operation == "native" and row.title_id not in request.title_ids:
                raise ValueError("unexpected title")
            if request.operation == "recent" and row.language not in request.languages:
                raise ValueError("unexpected language")
            primary = next(
                (m for m in title.mappings if m.namespace == row.namespace), None
            )
            if row.namespace is not None and (
                primary is None or primary.external_id != row.external_id
            ):
                raise ValueError("canonical title mismatch")
            mapped = next(
                (
                    m
                    for m in row.mappings
                    if primary is not None and m.mapping_id == primary.mapping_id
                ),
                None,
            )
            if (row.season, row.episode) != (
                (mapped.season, mapped.episode) if mapped else (None, None)
            ):
                raise ValueError("canonical episode mismatch")
            maps = {item.mapping_id for item in title.mappings}
            if any(
                m.entity_id != row.entity_id or m.mapping_id not in maps
                for m in row.mappings
            ):
                raise ValueError("invalid episode mapping")


def local_rows(response: Response) -> list[dict]:
    """Only the consumer chooses a mode/category and formats magnets."""
    return [
        dict(
            row.model_dump(),
            mode="download",
            category=2000
            if row.kind == "movie"
            else 5070
            if row.provider == "aniworld.to"
            else 5000,
        )
        for row in response.rows
    ]
