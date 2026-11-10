"""Generate one bounded media input offline; no downloaded provider bytes."""

import os
import subprocess
from pathlib import Path

root = Path("/generated")
root.mkdir(parents=True, exist_ok=True)
target = root / "generated.mp4"
if target.exists():
    raise ValueError("acceptance requires fresh disposable volumes")
subprocess.run(
    [
        "ffmpeg",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=320x180:rate=1",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=44100",
        "-t",
        "601",
        "-c:v",
        "libx264",
        "-threads",
        "1",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        "-n",
        str(target),
    ],
    check=True,
    timeout=60,
)
assert 0 < target.stat().st_size <= 16 * 1024**2
os.chown(root, 1000, 1000)
os.chown(target, 1000, 1000)
Path("/library").mkdir(parents=True, exist_ok=True)
os.chown("/library", 1000, 1000)
print("generated one 601-second test-pattern/sine MP4; no network")
