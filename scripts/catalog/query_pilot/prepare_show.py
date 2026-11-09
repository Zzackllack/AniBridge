"""Prepare fresh disposable one-title configuration; never collect on startup."""

import json
import os
import shlex
from pathlib import Path

from catalog_core.files import atomic_write

from catalog_worker.config import load
from catalog_worker.pilot_seed import prepare


def env_value(path: Path, name: str) -> str | None:
    """Read one generated dotenv value without importing a dotenv parser."""
    for line in path.read_text().splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == name:
            return shlex.split(value)[0]
    return None


root = Path("/config")
worker = root / "worker.json"
client_env = root / "client.env"
origin = os.environ["PILOT_PROVIDER_ORIGIN"]
source = os.environ["PILOT_SOURCE_ID"]
canonical = os.environ.get("PILOT_CANONICAL_TV", "off")
if worker.exists():
    config = load(worker)
    if (
        config.providers != {"aniworld.to": origin}
        or config.source_id != source
        or config.canonical_sources.get("tv") != canonical
        or env_value(client_env, "CATALOG_SOURCE_ID") != source
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
    lines = []
    for line in client_env.read_text().splitlines():
        if line.startswith("CATALOG_MODE="):
            lines.append("CATALOG_MODE=query")
        elif line.startswith("CATALOG_SOURCE_ID="):
            lines.append(f"CATALOG_SOURCE_ID={shlex.quote(source)}")
        else:
            lines.append(line)
    atomic_write(client_env, ("\n".join(lines) + "\n").encode())
    if os.geteuid() == 0:
        for path in (worker, client_env):
            os.chown(path, 1000, 1000)
print(json.dumps({"prepared": True, "collection": "explicit separate command"}))
