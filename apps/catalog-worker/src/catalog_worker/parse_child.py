"""Private bounded parser process; communicates normalized records only."""

import json
import sys
from dataclasses import asdict
from pathlib import Path

from catalog_core.diagnostics import phase
from catalog_core.json_codec import dumps
from catalog_core.supervisor import limit_child

from .adapters import adapter


def main() -> None:
    limit_child()
    source, destination, kind, page_path, *providers = sys.argv[1:]
    provider = providers[0] if providers else "aniworld.to"
    body = Path(source).read_bytes()
    options = (
        {
            "origin": providers[1],
            "sitemap_origins": tuple(json.loads(providers[2]))
            if len(providers) > 2
            else (),
        }
        if provider == "megakino"
        else {}
    )
    if kind == "signal":
        from catalog_core.providers.recent import parse as parse_recent

    page = (
        parse_recent(body, provider, providers[1])
        if kind == "signal"
        else adapter(provider).parse(body, kind, page_path, **options)
    )
    Path(destination).write_bytes(dumps(asdict(page)))


if __name__ == "__main__":
    with phase("parse"):
        main()
