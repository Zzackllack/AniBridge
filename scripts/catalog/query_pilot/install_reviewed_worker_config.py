"""Install reviewed config bytes while the pilot is stopped; never touch tokens."""

import argparse
import os
from pathlib import Path

from catalog_core.files import atomic_write


def install(
    plan: Path, operator: Path, config: Path, *, rollback: bool = False
) -> None:
    candidate = (plan / "worker-candidate.json").read_bytes()
    targets = (
        (operator / "worker.json", plan / "operator-rollback.json"),
        (config / "worker.json", plan / "volume-rollback.json"),
    )
    reviewed = []
    # Check both locations before changing either. Initializer startup copies the
    # operator file over the volume, so an independently edited source is a veto.
    for target, original in targets:
        before = original.read_bytes()
        # A previous I/O failure can leave one reviewed location updated. Allow
        # either reviewed version so retry/rollback can repair that partial step.
        if target.is_symlink() or target.read_bytes() not in (before, candidate):
            raise ValueError("configuration changed since review")
        reviewed.append((target, before if rollback else candidate, target.stat()))
    previous_mask = os.umask(0o077)
    try:
        for target, data, owner in reviewed:
            atomic_write(target, data)
            os.chown(target, owner.st_uid, owner.st_gid)
            target.chmod(0o600)
    finally:
        os.umask(previous_mask)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--operator", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()
    install(args.plan, args.operator, args.config, rollback=args.rollback)


if __name__ == "__main__":
    main()
