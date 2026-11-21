"""Package manager detection."""

import os
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


_DETECTED: list[dict[str, str | None]] | None = None


def detect_managers(refresh: bool = False) -> list[dict[str, str | None]]:
    """Detect supported package managers, probing each once per process."""
    global _DETECTED
    if _DETECTED is not None and not refresh:
        return [dict(entry) for entry in _DETECTED]
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
    _DETECTED = results
    return [dict(entry) for entry in results]


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
    """Read upgradable packages from locally cached apt metadata; never refresh it."""
    try:
        result = run_command(
            ["apt", "list", "--upgradable"], timeout=10, env={**os.environ, "LC_ALL": "C"}
        )
        if result.returncode:
            return {
                "manager": "apt",
                "available": False,
                "error": result.stderr.strip() or "apt failed",
            }
        lines = [
            line
            for line in result.stdout.splitlines()
            if "/" in line and "upgradable" in line.lower()
        ]
        return {
            "manager": "apt",
            "available": True,
            "upgradable_count": len(lines),
            "upgradable": lines[:20],
            "note": "Based on locally cached metadata; it may be stale.",
        }
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"manager": "apt", "available": False, "error": str(exc)}


def check_updates_dnf() -> dict[str, object]:
    try:
        r = run_command(
            ["dnf", "--cacheonly", "-q", "check-update"],
            timeout=15,
            env={**os.environ, "LC_ALL": "C"},
        )
        # dnf check-update returns 100 if updates available, 0 if none
        if r.returncode in (0, 100):
            lines = [l for l in r.stdout.splitlines() if l.strip() and not l.startswith("Last")]
            import re

            packages = [line for line in lines if re.match(r"^\S+\.\S+\s+\S+\s+\S+", line)]
            count = len(packages)
            if r.returncode == 100 and not packages:
                return {
                    "manager": "dnf",
                    "available": False,
                    "error": "Updates were reported but package output could not be parsed",
                }
            return {
                "manager": "dnf",
                "available": True,
                "upgradable_count": count,
                "details": packages[:20],
                "note": "Based on locally cached metadata; it may be stale.",
            }
    except Exception as e:
        return {"manager": "dnf", "available": False, "error": str(e)}
    return {"manager": "dnf", "available": False}


def check_updates_generic(manager: str) -> dict[str, object]:
    if manager == "apt":
        return check_updates_apt()
    if manager == "dnf":
        return check_updates_dnf()
    if manager == "pacman":
        try:
            result = run_command(["pacman", "-Qu"], timeout=10, env={**os.environ, "LC_ALL": "C"})
            if result.returncode == 0 or (result.returncode == 1 and not result.stderr.strip()):
                lines = [line for line in result.stdout.splitlines() if line.strip()]
                return {
                    "manager": "pacman",
                    "available": True,
                    "upgradable_count": len(lines),
                    "upgradable": lines[:20],
                    "note": "Based on locally cached metadata; it may be stale.",
                }
            return {
                "manager": "pacman",
                "available": False,
                "error": result.stderr.strip() or "pacman failed",
            }
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"manager": "pacman", "available": False, "error": str(exc)}
    return {
        "manager": manager,
        "available": False,
        "note": "Update check not implemented for this manager — run manually",
    }


def list_installed_packages(manager: str, limit: int = 20) -> list[str]:
    commands = {
        "apt": ["apt", "list", "--installed"],
        "dnf": ["dnf", "--cacheonly", "-q", "list", "installed"],
        "pacman": ["pacman", "-Q"],
        "brew": ["brew", "list"],
    }
    if manager not in commands:
        raise ValueError(f"Listing packages is not supported for {manager}")
    if not shutil.which(commands[manager][0]):
        raise FileNotFoundError(f"Package manager not found: {manager}")
    try:
        result = run_command(commands[manager], timeout=10)
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Package listing timed out for {manager}") from exc
    if result.returncode:
        raise RuntimeError(f"Package listing failed: {result.stderr.strip() or manager}")
    lines = result.stdout.splitlines()
    if manager == "apt":
        lines = [line for line in lines if "/" in line]
    return lines[:limit]
