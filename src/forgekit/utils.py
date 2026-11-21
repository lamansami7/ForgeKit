"""Utility helpers."""

import re
import socket
import subprocess
from pathlib import Path


def format_bytes(num_bytes: int | float) -> str:
    """Format bytes to human readable."""
    if num_bytes < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB", "PB"):
        if abs(num_bytes) < 1024.0:
            if unit == "B":
                return f"{int(num_bytes)} {unit}"
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} EB"


def format_duration(seconds: float) -> str:
    """Format seconds to human duration."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s:
        parts.append(f"{s}s")
    return " ".join(parts) if parts else "0s"


def run_command(
    cmd: list[str],
    cwd: Path | str | None = None,
    timeout: int = 15,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Run a subprocess command safely."""
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )


def which(cmd: str) -> str | None:
    """Find executable in PATH."""
    import shutil

    return shutil.which(cmd)


def is_valid_hostname(hostname: str) -> bool:
    if len(hostname) > 253:
        return False
    # allow IP or hostname
    try:
        socket.inet_aton(hostname)
        return True
    except OSError:
        pass
    # ipv6 check
    try:
        socket.inet_pton(socket.AF_INET6, hostname)
        return True
    except OSError:
        pass
    pattern = re.compile(
        r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.?$"
    )
    return bool(pattern.match(hostname))


def redact_url(url: str) -> str:
    """Redact credentials from URL."""
    # e.g. https://user:pass@host -> https://***@host
    return re.sub(r"://[^@/\s]+@", "://***@", url)


def safe_read_text(path: Path, max_bytes: int = 1024 * 1024) -> str | None:
    try:
        if path.stat().st_size > max_bytes:
            return None
        return path.read_text(errors="ignore")
    except Exception:
        return None
