from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_application_imports_in_a_fresh_process(tmp_path: Path) -> None:
    env = os.environ.copy()
    env.update(
        {
            "ANIWORLD_INSTALL_FOLDER": str(tmp_path / "aniworld"),
            "DATA_DIR": str(tmp_path / "data"),
            "DOWNLOAD_DIR": str(tmp_path / "downloads"),
        }
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.main; print(app.main.app.title)",
        ],
        check=False,
        capture_output=True,
        env=env,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "AniBridge-Minimal" in result.stdout
