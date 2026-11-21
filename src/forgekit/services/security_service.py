"""Security diagnostics — non-invasive checks."""

import os
import re
import stat
from pathlib import Path

from forgekit.core.permissions import check_ssh_permissions
from forgekit.platform import is_root
from forgekit.services.package_service import check_updates_generic, primary_manager


def check_security(path: Path | None = None) -> list[dict[str, str]]:
    """Run all security checks, return findings."""
    findings: list[dict[str, str]] = []

    # 1. Root check
    if is_root():
        findings.append(
            {
                "level": "warn",
                "check": "privilege",
                "message": "Running as root — avoid running ForgeKit as root unless necessary",
                "fix": "Run as regular user with sudo only when needed",
            }
        )
    else:
        findings.append(
            {
                "level": "info",
                "check": "privilege",
                "message": "Not running as root — good",
                "fix": "",
            }
        )

    # 2. SSH permissions
    ssh_issues = check_ssh_permissions()
    if ssh_issues:
        for iss in ssh_issues:
            findings.append(
                {
                    "level": iss.get("severity", "warn"),
                    "check": "ssh_permissions",
                    "message": f"{iss['path']}: {iss['issue']}",
                    "fix": "Review permissions for this specific path; do not change public keys blindly",
                }
            )
    else:
        # Check if .ssh exists
        ssh_dir = Path.home() / ".ssh"
        if ssh_dir.exists():
            findings.append(
                {
                    "level": "pass",
                    "check": "ssh_permissions",
                    "message": "SSH permissions look OK",
                    "fix": "",
                }
            )
        else:
            findings.append(
                {
                    "level": "info",
                    "check": "ssh_permissions",
                    "message": "No ~/.ssh directory found",
                    "fix": "",
                }
            )

    # Bounded traversal: actually prune exclusions and depth instead of merely
    # skipping entries after descending into them.
    scan_root = path or Path.home()
    world_writable: list[tuple[str, str, bool]] = []
    count = 0
    incomplete = False

    def onerror(_error: OSError) -> None:
        nonlocal incomplete
        incomplete = True

    def inspect(item: Path) -> None:
        nonlocal count, incomplete
        try:
            mode = item.lstat().st_mode
            count += 1
            if mode & stat.S_IWOTH and (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                kind = "directory" if stat.S_ISDIR(mode) else "regular file"
                world_writable.append((str(item), kind, bool(mode & stat.S_ISVTX)))
        except OSError:
            incomplete = True

    if scan_root.is_file():
        inspect(scan_root)
    else:
        for directory, dirs, files in os.walk(
            scan_root, topdown=True, followlinks=False, onerror=onerror
        ):
            if count >= 1000:
                incomplete = True
                break
            inspect(Path(directory))
            depth = len(Path(directory).relative_to(scan_root).parts)
            dirs[:] = [
                d
                for d in dirs
                if d not in {".git", "node_modules", ".cache"}
                and not (Path(directory) / d).is_symlink()
            ]
            if path is None and depth >= 3:
                if dirs:
                    incomplete = True
                dirs[:] = []
            for name in files:
                if count >= 1000:
                    incomplete = True
                    break
                inspect(Path(directory) / name)
            if count >= 1000:
                break
    for filename, kind, sticky in world_writable[:5]:
        findings.append(
            {
                "level": "info" if kind == "directory" and sticky else "warn",
                "check": "world_writable",
                "message": f"World-writable {kind}: {filename}"
                + (" (sticky bit set)" if kind == "directory" and sticky else ""),
                "fix": "Review permissions; consider removing other-write access",
            }
        )
    if len(world_writable) > 5:
        findings.append(
            {
                "level": "info",
                "check": "world_writable",
                "message": f"... and {len(world_writable) - 5} more",
                "fix": "",
            }
        )
    if not world_writable:
        findings.append(
            {
                "level": "info",
                "check": "world_writable",
                "message": "No world-writable files or directories found in inspected scope",
                "fix": "",
            }
        )
    if incomplete:
        findings.append(
            {
                "level": "warn",
                "check": "world_writable",
                "message": "Scan was limited or some paths were inaccessible; results are incomplete",
                "fix": "",
            }
        )

    # 4. Firewall status
    fw_findings = check_firewall()
    findings.extend(fw_findings)

    # 5. System updates
    upd = check_updates_available()
    findings.append(upd)

    # 6. Risky config patterns if path provided
    if path and path.is_file():
        risky = scan_risky_config(path)
        findings.extend(risky)

    return findings


def check_firewall() -> list[dict[str, str]]:
    """Observe available firewall tools without elevating privileges or modifying rules."""
    import shutil
    import subprocess

    def finding(level: str, message: str, fix: str = "") -> list[dict[str, str]]:
        return [{"level": level, "check": "firewall", "message": message, "fix": fix}]

    if shutil.which("ufw"):
        try:
            result = subprocess.run(["ufw", "status"], capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return finding("info", f"ufw status unavailable ({type(exc).__name__})")
        output = (result.stdout + result.stderr).lower()
        if result.returncode != 0:
            return finding("info", "ufw status unavailable (permissions or command error)")
        if re.search(r"status:\s*inactive\b", output):
            return finding(
                "warn", "ufw is installed but inactive", "Review rules before enabling ufw"
            )
        if re.search(r"status:\s*active\b", output):
            return finding("pass", "ufw is active")
        return finding("info", "ufw status could not be determined")

    if shutil.which("firewall-cmd"):
        try:
            result = subprocess.run(
                ["firewall-cmd", "--state"], capture_output=True, text=True, timeout=5
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return finding("info", f"firewalld status unavailable ({type(exc).__name__})")
        state = (result.stdout or result.stderr).strip().lower()
        if result.returncode == 0 and state == "running":
            return finding("pass", "firewalld is running")
        if state == "not running":
            return finding("warn", "firewalld is not running", "Review firewall configuration")
        return finding("info", "firewalld status unavailable (permissions or command error)")

    if shutil.which("iptables"):
        return finding(
            "info",
            "iptables found but status unknown (requires permission to inspect)",
            "Review firewall rules manually",
        )
    return finding(
        "info",
        "No common firewall tool detected (ufw/firewalld/iptables)",
        "Review firewall configuration manually",
    )


def check_updates_available() -> dict[str, str]:
    """Use cached package metadata only, and distinguish unavailable from zero updates."""
    manager = primary_manager()
    if not manager or not isinstance(manager.get("name"), str):
        return {
            "level": "info",
            "check": "updates",
            "message": "No supported package manager found for update check",
            "fix": "",
        }
    name = manager["name"]
    result = check_updates_generic(name)
    count = result.get("upgradable_count")
    if result.get("available") and isinstance(count, int):
        return {
            "level": "warn" if count else "info",
            "check": "updates",
            "message": f"{count} updates available via {name} (cached metadata may be stale)",
            "fix": f"Review and run: {manager['update_cmd']}" if count else "",
        }
    reason = result.get("error") or result.get("note") or "check manually"
    return {
        "level": "info",
        "check": "updates",
        "message": f"Update check unavailable for {name}: {reason}",
        "fix": "Check your package manager manually",
    }


def scan_risky_config(path: Path) -> list[dict[str, str]]:
    """Check at most one MiB of an explicitly selected file without displaying values."""
    max_bytes = 1024 * 1024
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError(f"Not a regular file: {path}")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    try:
        actual = os.fstat(fd)
        if not stat.S_ISREG(actual.st_mode) or (actual.st_dev, actual.st_ino) != (
            before.st_dev,
            before.st_ino,
        ):
            raise ValueError(f"File changed before it could be scanned: {path}")
        with os.fdopen(fd, "rb") as stream:
            fd = -1
            content_bytes = stream.read(max_bytes + 1)
    finally:
        if fd >= 0:
            os.close(fd)
    if len(content_bytes) > max_bytes:
        raise ValueError(f"File is too large to scan (limit {max_bytes} bytes): {path}")
    content = content_bytes.decode("utf-8", errors="replace")
    findings: list[dict[str, str]] = []
    patterns = [
        (r"password\s*=\s*[\"']?.+", "Possible hardcoded password", "warn"),
        (r"api[_-]?key\s*[:=]\s*[\"']?.+", "Possible hardcoded API key", "warn"),
        (r"secret\s*[:=]\s*[\"']?.+", "Possible hardcoded secret", "warn"),
        (r"chmod\s+777", "Overly permissive chmod 777", "fail"),
        (r"PermitRootLogin\s+yes", "SSH PermitRootLogin yes is risky", "warn"),
        (
            r"PasswordAuthentication\s+yes",
            "PasswordAuthentication yes — consider key-based auth",
            "info",
        ),
    ]
    for pattern, message, level in patterns:
        if re.search(pattern, content, re.IGNORECASE):
            findings.append(
                {
                    "level": level,
                    "check": "config_pattern",
                    "message": f"{message} in {path.name}",
                    "fix": "Review and remove sensitive values; use environment variables or secret management",
                }
            )
    return findings
