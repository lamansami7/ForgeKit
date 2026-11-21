"""Environment detection."""

import os
import shutil
from dataclasses import dataclass


@dataclass
class EnvCheck:
    name: str
    found: bool
    version: str | None
    path: str | None
    details: str | None = None


def check_tool(cmd: str, version_args: list[str] | None = None) -> EnvCheck:
    path = shutil.which(cmd)
    if not path:
        return EnvCheck(name=cmd, found=False, version=None, path=None, details="not found in PATH")
    version: str | None = None
    try:
        import subprocess

        args = version_args or ["--version"]
        result = subprocess.run([cmd, *args], capture_output=True, text=True, timeout=5)
        out = (result.stdout or result.stderr or "").strip().splitlines()
        if out:
            version = out[0].strip()[:120]
    except Exception:
        pass
    return EnvCheck(name=cmd, found=True, version=version, path=path)


def path_entries() -> list[str]:
    return os.environ.get("PATH", "").split(os.pathsep)


def python_info() -> dict[str, str]:
    import platform
    import sys

    return {
        "version": platform.python_version(),
        "executable": sys.executable,
        "implementation": platform.python_implementation(),
    }
