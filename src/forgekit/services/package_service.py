"""Package manager detection."""

import shutil
import subprocess

from forgekit.utils import run_command

KNOWN_MANAGERS = {
    "apt": {
        "check": "apt",
        "version_arg": "--version",
        "update_cmd": "sudo apt update && sudo apt upgrade",
    },
    "dnf": {"check": "dnf", "version_arg": "--version", "update_cmd": "sudo dnf upgrade"},
    "yum": {"check": "yum", "version_arg": "--version", "update_cmd": "sudo yum update"},
    "pacman": {"check": "pacman", "version_arg": "--version", "update_cmd": "sudo pacman -Syu"},
    "zypper": {"check": "zypper", "version_arg": "--version", "update_cmd": "sudo zypper update"},
    "apk": {"check": "apk", "version_arg": "--version", "update_cmd": "sudo apk upgrade"},
    "brew": {
        "check": "brew",
        "version_arg": "--version",
        "update_cmd": "brew update && brew upgrade",
    },
}


def detect_managers() -> list[dict[str, str | None]]:
    results: list[dict[str, str | None]] = []
    for name, info in KNOWN_MANAGERS.items():
        path = shutil.which(info["check"])
        if path:
            version: str | None = None
            try:
                r = subprocess.run(
                    [info["check"], info["version_arg"]],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                out = (r.stdout or r.stderr or "").strip().splitlines()
                if out:
                    version = out[0][:120]
            except Exception:
                version = "unknown"
            results.append(
                {
                    "name": name,
                    "path": path,
                    "version": version,
                    "update_cmd": info["update_cmd"],
                    "available": True,
                }
            )
    return results


def primary_manager() -> dict[str, str | None] | None:
    managers = detect_managers()
    if not managers:
        return None
    # Prefer native Linux managers first
    priority = ["apt", "dnf", "yum", "pacman", "zypper", "apk", "brew"]
    for p in priority:
        for m in managers:
            if m["name"] == p:
                return m
    return managers[0]


def check_updates_apt() -> dict[str, object]:
    """Check apt updates without modifying system — read apt lists or use apt check."""
    info: dict[str, object] = {"manager": "apt", "available": False}
    try:
        # Try apt list --upgradable (read-only)
        r = run_command(["apt", "list", "--upgradable"], timeout=10)
        if r.returncode == 0:
            lines = [l for l in r.stdout.splitlines() if "/" in l and "upgradable" in l.lower()]
            info["upgradable_count"] = len(lines)
            info["upgradable"] = lines[:20]
            info["available"] = True
            return info
    except Exception:
        pass
    # Fallback: check if /var/lib/apt/lists exists
    from pathlib import Path

    if Path("/var/lib/apt/lists").exists():
        info["note"] = "Run 'apt list --upgradable' to see pending updates"
        info["available"] = True
    else:
        info["note"] = "No apt metadata found"
    return info


def check_updates_dnf() -> dict[str, object]:
    try:
        r = run_command(["dnf", "check-update"], timeout=15)
        # dnf check-update returns 100 if updates available, 0 if none
        if r.returncode in (0, 100):
            lines = [l for l in r.stdout.splitlines() if l.strip() and not l.startswith("Last")]
            count = len([l for l in lines if "." in l])
            return {
                "manager": "dnf",
                "available": True,
                "upgradable_count": count,
                "details": lines[:20],
            }
    except Exception as e:
        return {"manager": "dnf", "available": False, "error": str(e)}
    return {"manager": "dnf", "available": False}


def check_updates_generic(manager: str) -> dict[str, object]:
    if manager == "apt":
        return check_updates_apt()
    if manager == "dnf":
        return check_updates_dnf()
    return {
        "manager": manager,
        "available": False,
        "note": "Update check not implemented for this manager — run manually",
    }


def list_installed_packages(manager: str, limit: int = 20) -> list[str]:
    try:
        if manager == "apt":
            r = run_command(["apt", "list", "--installed"], timeout=10)
            if r.returncode == 0:
                return [l for l in r.stdout.splitlines() if "/" in l][:limit]
        elif manager == "dnf":
            r = run_command(["dnf", "list", "installed"], timeout=10)
            if r.returncode == 0:
                return r.stdout.splitlines()[:limit]
        elif manager == "pacman":
            r = run_command(["pacman", "-Q"], timeout=10)
            if r.returncode == 0:
                return r.stdout.splitlines()[:limit]
        elif manager == "brew":
            r = run_command(["brew", "list"], timeout=10)
            if r.returncode == 0:
                return r.stdout.splitlines()[:limit]
    except Exception:
        pass
    return []
