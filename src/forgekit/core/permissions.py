"""Permission helpers."""

import os
from pathlib import Path


def can_read(path: Path) -> bool:
    return os.access(str(path), os.R_OK)


def can_write(path: Path) -> bool:
    return os.access(str(path), os.W_OK)


def is_world_writable(path: Path) -> bool:
    try:
        st = path.stat()
        return bool(st.st_mode & 0o002)
    except Exception:
        return False


def check_ssh_permissions(home: Path | None = None) -> list[dict[str, str]]:
    """Check SSH directory/file permissions."""
    h = home or Path.home()
    ssh_dir = h / ".ssh"
    issues: list[dict[str, str]] = []
    if not ssh_dir.exists():
        return issues
    try:
        mode = ssh_dir.stat().st_mode & 0o777
        if mode != 0o700:
            issues.append(
                {
                    "path": str(ssh_dir),
                    "issue": f"expected 0700, got {oct(mode)}",
                    "severity": "warn",
                }
            )
    except Exception:
        pass
    for name in ("id_rsa", "id_ed25519", "id_ecdsa", "authorized_keys", "config"):
        p = ssh_dir / name
        if p.exists():
            try:
                m = p.stat().st_mode & 0o777
                if m & 0o077:
                    issues.append(
                        {"path": str(p), "issue": f"too permissive: {oct(m)}", "severity": "fail"}
                    )
            except Exception:
                pass
    return issues
