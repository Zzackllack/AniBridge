import sys
import os
from datetime import datetime
from pathlib import Path

class TerminalLogger:
    """
    Duplicates all stdout/stderr to a log file named with the current date in data/.
    """
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / f"terminal-{datetime.now().strftime('%Y-%m-%d')}.log"
        self.log_file = open(self.log_path, "a", buffering=1)
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = self
        sys.stderr = self


    def write(self, data):
        self._stdout.write(data)
        self.log_file.write(data)

    def isatty(self):
        return self._stdout.isatty()

    def flush(self):
        self._stdout.flush()
        self.log_file.flush()

    def close(self):
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        self.log_file.close()

# Usage (add to main entrypoint):
# from app.terminal_logger import TerminalLogger
# TerminalLogger(Path.cwd() / "data")
