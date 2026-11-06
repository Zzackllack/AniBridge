"""Verify a previous admission receipt before reusing any validated row proof."""

import hashlib
import re
from pathlib import Path

from catalog_core import schema
from catalog_core.diagnostics import phase
from catalog_core.json_codec import dumps, loads

from .config import Config
from .state import State


def policy(config: Config) -> dict:
    """Policy/validator changes invalidate even an otherwise unchanged artifact."""
    return {
        "validator": schema.VALIDATION_VERSION,
        "source_id": config.source_id,
        "sources": sorted(config.publication_sources),
    }


def receipt(config: Config, metadata: dict) -> str:
    """Stored privately only after complete admission and pointer publication."""
    return dumps(
        {**policy(config), "metadata": hashlib.sha256(dumps(metadata)).hexdigest()}
    ).decode()


def clone(
    config: Config, state: State, root: Path, destination: Path, now: int
) -> bool:
    """Missing/stale/tampered bases use full export and full independent admission."""
    from .read_catalog import lease

    stored = state.db.execute("SELECT receipt FROM publication_meta").fetchone()[0]
    if not stored:
        return False
    try:
        with phase("clone"), lease(root):
            metadata = loads((root / "current.json").read_bytes(), 65536)
            if (
                stored != receipt(config, metadata)
                or metadata["catalog_schema_version"] != 2
                or metadata["published_at"] > now
            ):
                return False
            name = metadata["database"]
            if not re.fullmatch(r"read-[0-9a-f]{64}\.sqlite", name):
                return False
            source = root / name
            if source.is_symlink():
                return False
            digest = hashlib.sha256()
            with source.open("rb") as original, destination.open("xb") as output:
                while chunk := original.read(1024 * 1024):
                    digest.update(chunk)
                    output.write(chunk)
            if digest.hexdigest() != metadata["artifact"]["sqlite_sha256"]:
                destination.unlink()
                return False
            return True
    except (OSError, ValueError, KeyError, TypeError):
        destination.unlink(missing_ok=True)
        return False
