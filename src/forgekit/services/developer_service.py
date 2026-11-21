"""Developer environment detection."""

import shutil
import subprocess

TOOL_CHECKS = {
    "python": {"cmd": "python3", "version_args": ["--version"], "alt": "python"},
    "pip": {"cmd": "pip", "version_args": ["--version"], "alt": "pip3"},
    "git": {"cmd": "git", "version_args": ["--version"]},
    "node": {"cmd": "node", "version_args": ["--version"]},
    "npm": {"cmd": "npm", "version_args": ["--version"]},
    "java": {"cmd": "java", "version_args": ["--version"]},
    "gcc": {"cmd": "gcc", "version_args": ["--version"]},
    "clang": {"cmd": "clang", "version_args": ["--version"]},
    "docker": {"cmd": "docker", "version_args": ["--version"]},
    "podman": {"cmd": "podman", "version_args": ["--version"]},
    "rustc": {"cmd": "rustc", "version_args": ["--version"], "label": "rust"},
    "cargo": {"cmd": "cargo", "version_args": ["--version"]},
    "go": {"cmd": "go", "version_args": ["version"]},
    "php": {"cmd": "php", "version_args": ["--version"]},
    "ruby": {"cmd": "ruby", "version_args": ["--version"]},
}


def check_tool(name: str, spec: dict[str, object]) -> dict[str, object]:
    cmd = spec["cmd"]  # type: ignore
    label = spec.get("label", name)  # type: ignore
    path = shutil.which(cmd)  # type: ignore
    # Try alt if not found
    if not path and "alt" in spec:
        alt = spec["alt"]  # type: ignore
        path = shutil.which(alt)  # type: ignore
        if path:
            cmd = alt  # type: ignore

    if not path:
        return {
            "name": label,
            "found": False,
            "path": None,
            "version": None,
            "details": "Not found in PATH",
        }

    version: str | None = None
    try:
        args = spec.get("version_args", ["--version"])  # type: ignore
        r = subprocess.run([cmd, *args], capture_output=True, text=True, timeout=5)  # type: ignore
        out = (r.stdout or r.stderr or "").strip().splitlines()
        if out:
            version = out[0][:150]
    except Exception as e:
        version = f"error: {e}"

    # Additional PATH check
    details = None
    if version and "not found" not in version.lower():
        details = "OK"

    return {"name": label, "found": True, "path": path, "version": version, "details": details}


def detect_all() -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for name, spec in TOOL_CHECKS.items():
        results.append(check_tool(name, spec))
    return results


def path_diagnostics() -> list[dict[str, str]]:
    import os

    issues: list[dict[str, str]] = []
    path = os.environ.get("PATH", "")
    entries = path.split(os.pathsep) if path else []
    if not entries or (len(entries) == 1 and entries[0] == ""):
        issues.append(
            {
                "level": "fail",
                "message": "PATH is empty or unset",
                "fix": "Check shell configuration",
            }
        )
        return issues

    # Check for duplicates
    seen = set()
    dups = set()
    for e in entries:
        if e in seen:
            dups.add(e)
        seen.add(e)
    if dups:
        issues.append(
            {
                "level": "warn",
                "message": f"Duplicate PATH entries: {', '.join(list(dups)[:3])}",
                "fix": "Clean up PATH in shell rc file",
            }
        )

    # Check non-existent directories in PATH
    missing = [e for e in entries if e and not __import__("pathlib").Path(e).exists()]
    if missing:
        issues.append(
            {
                "level": "warn",
                "message": f"PATH contains non-existent directories: {', '.join(missing[:3])}",
                "fix": "Remove missing entries from PATH",
            }
        )

    # Check common dev dirs
    import pathlib

    for cand in [pathlib.Path.home() / ".local" / "bin", pathlib.Path("/usr/local/bin")]:
        if cand.exists() and str(cand) not in entries:
            issues.append(
                {
                    "level": "info",
                    "message": f"{cand} exists but not in PATH",
                    "fix": f'Add to PATH: export PATH="$PATH:{cand}"',
                }
            )

    if not issues:
        issues.append({"level": "pass", "message": "PATH looks healthy", "fix": ""})

    return issues
