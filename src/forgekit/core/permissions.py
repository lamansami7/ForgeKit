"""Permission helpers for non-invasive diagnostics."""

import os
import stat
from pathlib import Path


def can_read(path: Path) -> bool:
    return os.access(str(path), os.R_OK)


def can_write(path: Path) -> bool:
    return os.access(str(path), os.W_OK)


def is_world_writable(path: Path) -> bool:
    try:
        mode = path.lstat().st_mode
        return not stat.S_ISLNK(mode) and bool(mode & stat.S_IWOTH)
    except OSError:
        return False


def check_ssh_permissions(home: Path | None = None) -> list[dict[str, str]]:
    """Report permission concerns without reading SSH files or following links."""
    ssh_dir = (home or Path.home()) / ".ssh"
    issues: list[dict[str, str]] = []
    try:
        mode = ssh_dir.lstat().st_mode
    except FileNotFoundError:
        return issues
    except OSError as exc:
        return [{"path": str(ssh_dir), "issue": f"could not inspect: {exc}", "severity": "warn"}]
    if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
        return [
            {
                "path": str(ssh_dir),
                "issue": "not a regular directory; permissions not checked",
                "severity": "warn",
            }
        ]
    if mode & 0o077:
        issues.append(
            {
                "path": str(ssh_dir),
                "issue": f"recommended mode 0700; found {oct(stat.S_IMODE(mode))}",
                "severity": "warn",
            }
        )
    for name in ("id_rsa", "id_ed25519", "id_ecdsa", "authorized_keys", "config"):
        path = ssh_dir / name
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            issues.append(
                {"path": str(path), "issue": f"could not inspect: {exc}", "severity": "warn"}
            )
            continue
        if not stat.S_ISREG(mode):
            issues.append(
                {
                    "path": str(path),
                    "issue": "not a regular file; permissions not checked",
                    "severity": "warn",
                }
            )
            continue
        unsafe = mode & (0o077 if name.startswith("id_") else 0o022)
        if unsafe:
            issues.append(
                {
                    "path": str(path),
                    "issue": f"permissions may be too open: {oct(stat.S_IMODE(mode))}",
                    "severity": "warn",
                }
            )
    return issues
