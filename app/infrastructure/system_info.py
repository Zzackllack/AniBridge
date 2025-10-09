from __future__ import annotations

import os
import sys
import socket
import platform
import shutil
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple
from loguru import logger

from app.utils.logger import config as configure_logger
from app.config import DATA_DIR, DOWNLOAD_DIR, IN_DOCKER

configure_logger()


def _read_file(path: str, max_bytes: int = 200_000) -> str:
    try:
        with open(path, "rb") as f:
            return f.read(max_bytes).decode(errors="replace")
    except Exception:
        return ""


def _parse_os_release() -> Dict[str, str]:
    out: Dict[str, str] = {}
    text = _read_file("/etc/os-release")
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
    return out


def _disk_usage(path: str) -> Optional[Tuple[int, int, int]]:
    try:
        du = shutil.disk_usage(path)
        return du.total, du.used, du.free
    except Exception:
        return None


def _default_route_ip() -> Optional[str]:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 53))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


def _mask_env_value(key: str, val: str) -> str:
    k = (key or "").lower()
    # Use network mask for proxy URLs if available
    try:
        if any(k.endswith(s) for s in ("_url",)) or "proxy" in k:
            from app.infrastructure.network import _mask  # type: ignore

            return _mask(val)
    except Exception:
        pass
    # Generic secret patterns
    secret_words = (
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "apikey",
        "api_key",
        "key",
    )
    if any(sw in k for sw in secret_words):
        if not val:
            return val
        # Mask all but first 3 and last 2 chars
        if len(val) <= 6:
            return "****"
        return val[:3] + "****" + val[-2:]
    return val


def log_full_system_report() -> None:
    """Emit a detailed, one-shot system report for diagnostics."""
    try:
        # Use timezone-aware UTC timestamp (PEP 495) and render with 'Z'
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        logger.info(f"SysInfo: timestamp_utc={now}")

        # Python / process
        logger.info(
            f"SysInfo: python={sys.version.split()[0]} exec={sys.executable} pid={os.getpid()} cwd={os.getcwd()}"
        )
        logger.info(
            f"SysInfo: argv={sys.argv} user_uid={os.getuid() if hasattr(os,'getuid') else 'n/a'} group_gid={os.getgid() if hasattr(os,'getgid') else 'n/a'}"
        )

        # OS / platform
        uname = platform.uname()
        logger.info(
            f"SysInfo: os={uname.system} release={uname.release} version={uname.version} machine={uname.machine} processor={uname.processor}"
        )
        try:
            plat = platform.platform()
            logger.info(f"SysInfo: platform={plat}")
        except Exception:
            pass

        osrel = _parse_os_release()
        if osrel:
            pretty = (
                osrel.get("PRETTY_NAME")
                or " ".join([osrel.get("NAME", ""), osrel.get("VERSION", "")]).strip()
            )
            logger.info(f"SysInfo: os_release={pretty} id={osrel.get('ID','')}")

        # Container / cgroup
        logger.info(f"SysInfo: in_docker={IN_DOCKER}")
        cg = _read_file("/proc/1/cgroup", max_bytes=5000)
        if cg:
            first = "|".join(cg.splitlines()[:3])
            logger.info(f"SysInfo: cgroup_snippet={first}")

        # CPU / cores
        try:
            cpuinfo = _read_file("/proc/cpuinfo", max_bytes=5000)
            model = ""
            for line in cpuinfo.splitlines():
                if ":" in line and line.lower().startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                    break
            logger.info(
                f"SysInfo: cpu_cores={os.cpu_count()} model={model or uname.processor}"
            )
        except Exception:
            logger.info(f"SysInfo: cpu_cores={os.cpu_count()}")

        # Memory
        meminfo = _read_file("/proc/meminfo", max_bytes=5000)
        if meminfo:
            lines = {
                l.split(":", 1)[0]: l.split(":", 1)[1].strip()
                for l in meminfo.splitlines()
                if ":" in l
            }
            mt = lines.get("MemTotal")
            ma = lines.get("MemAvailable") or lines.get("MemFree")
            logger.info(f"SysInfo: mem_total={mt} mem_available={ma}")

        # Disk usage
        for label, path in (
            ("root", "/"),
            ("data_dir", str(DATA_DIR)),
            ("download_dir", str(DOWNLOAD_DIR)),
        ):
            du = _disk_usage(path)
            if du:
                t, u, f = du
                logger.info(
                    f"SysInfo: disk_{label} total={t} used={u} free={f} path={path}"
                )

        # Network
        try:
            hostname = socket.gethostname()
            fqdn = socket.getfqdn()
            defip = _default_route_ip()
            logger.info(f"SysInfo: hostname={hostname} fqdn={fqdn} default_ip={defip}")
        except Exception:
            pass
        try:
            ifnames = []
            for name in os.listdir("/sys/class/net"):
                ifnames.append(name)
            if ifnames:
                logger.info(f"SysInfo: interfaces={ifnames}")
        except Exception:
            pass

        # Mounts (snippet)
        mounts = _read_file("/proc/mounts", max_bytes=20000)
        if mounts:
            first = "|".join(mounts.splitlines()[:10])
            logger.info(f"SysInfo: mounts_snippet={first}")

        # Environment (masked)
        try:
            masked = {k: _mask_env_value(k, v) for k, v in os.environ.items()}
            logger.debug(f"SysInfo: env={masked}")
        except Exception:
            pass

        # Installed packages (best effort)
        try:
            import importlib.metadata as importlib_metadata  # py3.8+

            pkgs = sorted(
                [
                    f"{d.metadata['Name']}=={d.version}"
                    for d in importlib_metadata.distributions()
                ]
            )
            # Limit to avoid huge logs
            head = pkgs[:100]
            more = max(0, len(pkgs) - len(head))
            logger.debug(f"SysInfo: packages(first100)={head} more={more}")
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"SysInfo: failed to log full system report: {e}")
