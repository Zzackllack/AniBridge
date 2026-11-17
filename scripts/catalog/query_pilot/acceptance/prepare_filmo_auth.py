"""Create private disposable qBittorrent credentials for Filmo acceptance."""

from __future__ import annotations

import json
import os
import secrets
import tempfile
from pathlib import Path


def write_private(path: Path, content: str, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
    except Exception:
        path.unlink(missing_ok=True)
        raise


def prepare(directory: Path | None = None) -> Path:
    if directory is None:
        directory = Path(tempfile.mkdtemp(prefix="anibridge-filmo-acceptance-"))
    else:
        directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    directory.chmod(0o700)

    username = f"pilot-{secrets.token_hex(8)}"
    password = secrets.token_urlsafe(24)
    session_secret = secrets.token_urlsafe(48)
    environment = (
        f"QBIT_USERNAME={username}\n"
        f"QBIT_PASSWORD={password}\n"
        f"QBIT_SESSION_SECRET={session_secret}\n"
        "QBIT_COOKIE_SECURE=false\n"
    )
    auth = json.dumps({"username": username, "password": password}) + "\n"
    write_private(directory / "api.env", environment, 0o600)
    # Docker mounts this one file into a UID-1000 API container. The private
    # parent directory keeps the readable file inaccessible on the host.
    write_private(directory / "qbit.json", auth, 0o444)
    return directory


if __name__ == "__main__":
    print(prepare())
