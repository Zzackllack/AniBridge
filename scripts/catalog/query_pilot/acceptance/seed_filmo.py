"""Seed and publish one reviewed synthetic movie through worker code paths."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from catalog_core.files import ProcessLock
from catalog_core import identity
from catalog_core.providers import filmo
from catalog_worker.config import load
from catalog_worker.pilot_seed import prepare
from catalog_worker.read_catalog import provider_root, publish
from catalog_worker.state import State
from filmo_fixture import (
    DETAIL_HTML,
    LISTING_HTML,
    MOVIE_PATH,
    ORIGIN,
    canonical_mapping_rows,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("config_root", type=Path)
    args = parser.parse_args()
    config_file = prepare(args.config_root, "filmo.to")
    if os.geteuid() == 0:
        os.setgid(1000)
        os.setuid(1000)
    lock = ProcessLock(Path("/state") / "worker.lock")
    try:
        seed(config_file)
    finally:
        lock.close()


def seed(config_file: Path) -> None:
    config = load(config_file)
    if (
        config.source_id != "private-fixture"
        or config.providers.get("filmo.to") != ORIGIN
        or "synthetic-v1" not in config.publication_sources
    ):
        raise ValueError("worker config is not the isolated Filmo fixture config")

    state_path = config.state_dir / "filmo.to.sqlite"
    published_root = provider_root(config.output_dir, "filmo.to")
    if state_path.exists() or (published_root / "current.json").exists():
        raise ValueError("Filmo acceptance requires a fresh disposable state volume")

    state = State(state_path, "filmo.to")
    now = int(time.time())
    try:
        listing = filmo.parse(
            LISTING_HTML.encode(), "listing", "/movies", origin=ORIGIN
        )
        if len(listing.links) != 1 or listing.links[0].path != MOVIE_PATH:
            raise ValueError("synthetic listing did not yield the declared movie")
        state.listing(listing, now)
        work = state.claim(now)
        if work is None or work["path"] != MOVIE_PATH:
            raise ValueError("worker did not admit the synthetic detail path")
        detail = filmo.parse(DETAIL_HTML.encode(), "detail", MOVIE_PATH, origin=ORIGIN)
        if detail.title != "Night of the Living Dead" or detail.year != 1968:
            raise ValueError("synthetic movie metadata did not parse as declared")
        if {offer["native_id"] for offer in detail.offers} != {"42", "84"}:
            raise ValueError("synthetic provider variants did not parse as declared")
        state.detail(work, detail, now)

        title_id = identity.title_id("filmo.to", MOVIE_PATH)
        state.db.executemany(
            "INSERT INTO canonical_title VALUES(?,?,?,?,?,?,?)",
            canonical_mapping_rows(title_id, now),
        )
        state.db.commit()
        result = publish(config, state, now, full=True)
        current = json.loads((published_root / "current.json").read_text())
        if (
            current.get("provider") != "filmo.to"
            or result.get("provider") != "filmo.to"
        ):
            raise ValueError("published fixture catalog has the wrong provider")
        print("published one synthetic Filmo movie and two declared variants")
    finally:
        state.close()


if __name__ == "__main__":
    main()
