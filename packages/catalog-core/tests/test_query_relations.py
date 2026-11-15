"""Fixed SQL templates stay bound, and only base relations receive index hints."""

import re
import sqlite3
from contextlib import contextmanager

from catalog_core import fixtures, query, schema


class Store:
    """Minimal read store: one catalog per provider, no observation overlay."""

    def __init__(self, db, metadata, provider="aniworld.to"):
        self.db, self.metadata, self.provider = db, metadata, provider
        self.providers = (provider,)

    @contextmanager
    def acquire(self):
        private = sqlite3.connect(":memory:")
        private.row_factory = sqlite3.Row
        try:
            yield {self.provider: (self.db, self.metadata)}, private
        finally:
            private.close()


class RecordingStore(Store):
    """Record every statement so a test can prove what reached SQLite."""

    def __init__(self, db, metadata, provider="aniworld.to"):
        super().__init__(db, metadata, provider)
        self.statements = []

    @contextmanager
    def acquire(self):
        inner = self.db

        class Recorded:
            def __getattr__(self, name):
                return getattr(inner, name)

            def execute(self, sql, args=()):
                self_store.statements.append(sql)
                return inner.execute(sql, args)

        self_store = self
        with super().acquire() as (_catalogs, private):
            yield {self.provider: (Recorded(), self.metadata)}, private


def test_provider_name_never_reaches_the_category_statement(tmp_path):
    _, payload, _, _ = fixtures.build(tmp_path)
    db = schema.connect(tmp_path / "fixture.sqlite")
    hostile = "aniworld.to' OR '1'='1"
    store = RecordingStore(db, payload, provider=hostile)
    selected, total, _ = query.query(
        store,
        query.parse({"t": "search", "cat": "5070"}),
        now=1800000000,
    )
    assert store.statements and all(hostile not in sql for sql in store.statements)
    # Only AniWorld episodes carry the configured anime category; a name that
    # merely borrows the provider text must fall into the generic category.
    assert selected == [] and total == 0
    selected, total, _ = query.query(
        store, query.parse({"t": "search", "cat": "5000"}), now=1800000000
    )
    assert selected and total == 4


def test_compact_recent_query_keeps_the_physical_release_index(tmp_path):
    _, payload, _, _ = fixtures.build(tmp_path, schema_version=2)
    db = schema.connect(tmp_path / "fixture.sqlite")
    selected, total, _ = query.query(
        Store(db, payload), query.parse({"t": "search"}), now=1800000000
    )
    assert selected and total == 4


ATTACHED_TABLES = re.compile(
    r"\b(FROM|JOIN)\s+(release_data|release|entity_data|entity|title_data|title|"
    r"alias|canonical_title|canonical_episode)\b",
    re.IGNORECASE,
)


class Attached:
    """Stand-in for an opaque reader that exposes relations behind an alias.

    The API's MappingView owns whatever relation it attaches; core may not name
    an index on it, because a compact artifact exposes `release` as a view.
    """

    def __init__(self, catalog, alias="catalog_read_0"):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.execute(
            f"ATTACH DATABASE ? AS {alias}",
            (catalog.resolve().as_uri() + "?mode=ro&immutable=1",),
        )
        self.alias = alias
        self.observations = False

    def execute(self, sql, args=()):
        qualified = ATTACHED_TABLES.sub(
            lambda match: f"{match[1]} {self.alias}.{match[2]}", sql
        )
        return self.db.execute(qualified, args)

    def set_progress_handler(self, *args):
        self.db.set_progress_handler(*args)

    def oldest_release(self):
        return self.db.execute(
            f"SELECT min(first_seen_at) FROM {self.alias}.release"
        ).fetchone()[0]


def test_attached_reader_never_receives_a_hint_for_a_release_view(tmp_path):
    _, payload, _, _ = fixtures.build(tmp_path, schema_version=2)
    # A schema-2 artifact publishes `release` as a view over release_data, so a
    # "FROM <alias>.release INDEXED BY release_recent" hint fails outright.
    attached = Attached(tmp_path / "fixture.sqlite")
    selected, total, _ = query.query(
        Store(attached, payload), query.parse({"t": "search"}), now=1800000000
    )
    assert selected and total == 4
    assert all(row["provider"] == "aniworld.to" for row in selected)


def build_schema3(directory):
    """One compact schema-3 movie without a signed envelope (view-path fixture)."""
    from catalog_core import identity
    from catalog_core.compact import Writer

    directory.mkdir()
    path = directory / "catalog.sqlite"
    db = schema.create(path, version=3)
    title_path = "/films/123-example.html"
    title_id = identity.title_id("filmo.to", title_path)
    entity_id = identity.entity_id("filmo.to", title_path)
    mapping_id = identity.mapping_id("filmo.to", title_id, "tmdb-movie", "123")
    writer = Writer(db, 3)
    with db:
        writer.insert("catalog", (1, "filmo.to", 3, 1, 1800000000))
        writer.insert(
            "title",
            (
                title_id,
                title_path,
                "example",
                "Example",
                "example",
                "movie",
                2020,
                title_path,
                1800000000,
                "complete",
            ),
        )
        writer.insert(
            "entity",
            (
                entity_id,
                title_id,
                title_path,
                "movie",
                None,
                None,
                "Example",
                title_path,
                1800000000,
            ),
        )
        writer.insert(
            "release",
            (
                identity.release_id("filmo.to", entity_id, "de-dub"),
                entity_id,
                "de-dub",
                1800000000,
                1800000000,
            ),
        )
        writer.insert(
            "canonical_title",
            (
                mapping_id,
                title_id,
                "tmdb-movie",
                "123",
                "synthetic-v1",
                "reviewed",
                1800000000,
            ),
        )
    db.close()
    metadata = {
        "provider": "filmo.to",
        "catalog_schema_version": 3,
        "artifact": {"sqlite_sha256": "0" * 64},
        "counts": {"release": 1},
    }
    return path, metadata


def test_attached_schema3_view_path_needs_no_release_index_hint(tmp_path):
    path, metadata = build_schema3(tmp_path / "catalog")
    attached = Attached(path)
    selected, total, _ = query.query(
        Store(attached, metadata, provider="filmo.to"),
        query.parse({"t": "search"}),
        now=1800000000,
    )
    assert total == 1
    assert selected[0]["provider"] == "filmo.to"
    assert selected[0]["kind"] == "movie"
