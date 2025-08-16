import sys
import os
from datetime import datetime
from pathlib import Path


import threading


class TerminalLogger:
    """
    Singleton logger that duplicates all stdout/stderr to a single log file per run in data/.
    """

    _instance = None
    _lock = threading.Lock()
    _log_path = None

    def __new__(cls, log_dir: Path):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                # Use environment variable if set
                log_path_env = os.environ.get("ANIBRIDGE_LOG_PATH")
                if log_path_env:
                    cls._log_path = Path(log_path_env)
                else:
                    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    pid = os.getpid()
                    cls._log_path = log_dir / f"terminal-{ts}-{pid}.log"
                    os.environ["ANIBRIDGE_LOG_PATH"] = str(cls._log_path)
                cls._instance._init(log_dir)
            return cls._instance

    def _init(self, log_dir: Path):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.__class__._log_path
        self.log_file = open(str(self.log_path), "a", buffering=1)
        self._stdout = sys.stdout
        self._stderr = sys.stderr
        sys.stdout = self
        sys.stderr = self

    def write(self, data):
        self._stdout.write(data)
        # Remove ANSI color codes before writing to log file
        import re

        ansi_escape = re.compile(r"\x1B\[[0-9;]*[A-Za-z]")
        clean_data = ansi_escape.sub("", data)
        self.log_file.write(clean_data)

    def isatty(self):
        return self._stdout.isatty()

    def flush(self):
        self._stdout.flush()
        self.log_file.flush()

    def close(self):
        sys.stdout = self._stdout
        sys.stderr = self._stderr
        self.log_file.close()
