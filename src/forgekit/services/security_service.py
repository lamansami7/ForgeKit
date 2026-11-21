"""Security diagnostics — non-invasive checks."""

import re
from pathlib import Path

from forgekit.core.permissions import check_ssh_permissions, is_world_writable
from forgekit.platform import is_root
from forgekit.utils import safe_read_text


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
                    "fix": "chmod 700 ~/.ssh; chmod 600 ~/.ssh/id_* ~/.ssh/authorized_keys",
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

    # 3. World-writable files in selected locations
    scan_root = path or Path.home()
    # Limit scan to avoid huge traversal: check only top-level dotfiles and selected dir if provided
    # For home default, scan 2 levels with cap
    ww_files: list[str] = []
    try:
        max_scan = 1000
        count = 0
        for p in scan_root.rglob("*"):
            if count >= max_scan:
                break
            # Avoid descending into huge dirs
            if ".git" in p.parts or "node_modules" in p.parts or ".cache" in p.parts:
                continue
            try:
                if p.is_file() and is_world_writable(p):
                    ww_files.append(str(p))
                    if len(ww_files) >= 10:
                        break
            except (PermissionError, OSError):
                continue
            count += 1
            # Limit depth: only scan if user provided specific path, else shallow
            if scan_root == Path.home() and len(p.parts) - len(scan_root.parts) > 3:
                continue
    except (PermissionError, OSError):
        pass

    if ww_files:
        for f in ww_files[:5]:
            findings.append(
                {
                    "level": "warn",
                    "check": "world_writable",
                    "message": f"World-writable: {f}",
                    "fix": "chmod o-w <file> or review permissions",
                }
            )
        if len(ww_files) > 5:
            findings.append(
                {
                    "level": "info",
                    "check": "world_writable",
                    "message": f"... and {len(ww_files) - 5} more world-writable files",
                    "fix": "",
                }
            )
    else:
        findings.append(
            {
                "level": "pass",
                "check": "world_writable",
                "message": "No world-writable files found in scanned scope",
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
    import shutil
    import subprocess

    results: list[dict[str, str]] = []
    # Check ufw
    if shutil.which("ufw"):
        try:
            r = subprocess.run(["ufw", "status"], capture_output=True, text=True, timeout=5)
            out = (r.stdout + r.stderr).lower()
            if "inactive" in out:
                results.append(
                    {
                        "level": "warn",
                        "check": "firewall",
                        "message": "ufw is installed but inactive",
                        "fix": "sudo ufw enable (review rules first)",
                    }
                )
            elif "active" in out:
                results.append(
                    {"level": "pass", "check": "firewall", "message": "ufw is active", "fix": ""}
                )
            else:
                results.append(
                    {
                        "level": "info",
                        "check": "firewall",
                        "message": f"ufw status: {out[:100]}",
                        "fix": "",
                    }
                )
            return results
        except Exception:
            pass

    if shutil.which("firewall-cmd"):
        try:
            r = subprocess.run(
                ["firewall-cmd", "--state"], capture_output=True, text=True, timeout=5
            )
            if "running" in (r.stdout + r.stderr).lower():
                results.append(
                    {
                        "level": "pass",
                        "check": "firewall",
                        "message": "firewalld is running",
                        "fix": "",
                    }
                )
                return results
        except Exception:
            pass

    if shutil.which("iptables"):
        results.append(
            {
                "level": "info",
                "check": "firewall",
                "message": "iptables found but status unknown (requires root to inspect)",
                "fix": "sudo iptables -L to review rules",
            }
        )
        return results

    results.append(
        {
            "level": "info",
            "check": "firewall",
            "message": "No common firewall tool detected (ufw/firewalld/iptables)",
            "fix": "Consider enabling ufw or firewalld",
        }
    )
    return results


def check_updates_available() -> dict[str, str]:
    # Use package manager detection
    from forgekit.services.package_service import check_updates_generic, detect_managers

    managers = detect_managers()
    if not managers:
        return {
            "level": "info",
            "check": "updates",
            "message": "No supported package manager found for update check",
            "fix": "",
        }
    primary = managers[0]
    info = check_updates_generic(primary["name"])  # type: ignore
    count = info.get("upgradable_count")
    if count is not None and isinstance(count, int) and count > 0:
        return {
            "level": "warn",
            "check": "updates",
            "message": f"{count} updates available via {primary['name']}",
            "fix": f"Run: {primary['update_cmd']}",
        }
    if count == 0:
        return {
            "level": "pass",
            "check": "updates",
            "message": "System appears up to date (no pending updates detected)",
            "fix": "",
        }
    return {
        "level": "info",
        "check": "updates",
        "message": f"Update status for {primary['name']}: {info.get('note', 'check manually')}",
        "fix": f"Run: {primary['update_cmd']}",
    }


def scan_risky_config(path: Path) -> list[dict[str, str]]:
    content = safe_read_text(path)
    if not content:
        return []
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
    for pat, msg, level in patterns:
        if re.search(pat, content, re.IGNORECASE):
            findings.append(
                {
                    "level": level,
                    "check": "config_pattern",
                    "message": f"{msg} in {path.name}",
                    "fix": "Review and remove sensitive values; use environment variables or secret management",
                }
            )
    return findings
