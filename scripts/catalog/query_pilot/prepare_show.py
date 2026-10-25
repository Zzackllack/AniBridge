"""Prepare fresh disposable one-title configuration; never collect on startup."""

import json
import os
from pathlib import Path

from catalog_core.files import atomic_write
from catalog_worker.config import load
from catalog_worker.pilot_seed import prepare


root = Path("/config")
worker = root / "worker.json"
origin = os.environ["PILOT_PROVIDER_ORIGIN"]
source = os.environ["PILOT_SOURCE_ID"]
canonical = os.environ.get("PILOT_CANONICAL_TV", "off")
if worker.exists():
    config = load(worker)
    if (
        config.providers != {"aniworld.to": origin}
        or config.source_id != source
        or config.canonical_sources.get("tv") != canonical
        or json.loads((root / "client.json").read_text())["source_id"] != source
    ):
        raise ValueError("existing config differs; choose a fresh disposable project")
else:
    # Reuse the fixture's safe ownership/token handling, without its seed pass.
    prepare(root)
    body = json.loads(worker.read_text())
    body.update(
        providers={"aniworld.to": origin},
        source_id=source,
        canonical_sources={"tv": canonical, "movie": "off"},
        publication_sources=["skyhook-v1"] if canonical == "skyhook" else [],
    )
    atomic_write(worker, json.dumps(body).encode())
    load(worker)  # Reject invalid origin/source/canonical configuration locally.
    client = root / "client.json"
    body = json.loads(client.read_text())
    body["source_id"] = source
    atomic_write(client, json.dumps(body).encode())
    if os.geteuid() == 0:
        for path in (worker, client):
            os.chown(path, 1000, 1000)
print(json.dumps({"prepared": True, "collection": "explicit separate command"}))
