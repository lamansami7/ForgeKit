"""Platform detection and abstraction."""

import platform
from dataclasses import dataclass
from enum import StrEnum


class OS(StrEnum):
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PlatformInfo:
    os: OS
    system: str
    release: str
    version: str
    machine: str
    processor: str
    python_version: str
    is_linux: bool
    is_macos: bool
    is_windows: bool


def detect_os() -> OS:
    s = platform.system().lower()
    if s == "linux":
        return OS.LINUX
    if s == "darwin":
        return OS.MACOS
    if s == "windows":
        return OS.WINDOWS
    return OS.UNKNOWN


def get_platform_info() -> PlatformInfo:
    os_type = detect_os()
    return PlatformInfo(
        os=os_type,
        system=platform.system(),
        release=platform.release(),
        version=platform.version(),
        machine=platform.machine(),
        processor=platform.processor() or platform.machine(),
        python_version=platform.python_version(),
        is_linux=os_type == OS.LINUX,
        is_macos=os_type == OS.MACOS,
        is_windows=os_type == OS.WINDOWS,
    )


def is_root() -> bool:
    """Check if running as root."""
    try:
        import os as _os

        return _os.geteuid() == 0  # type: ignore[attr-defined]
    except AttributeError:
        return False


def get_current_user() -> str:
    import getpass

    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def get_hostname() -> str:
    try:
        return platform.node() or "unknown"
    except Exception:
        return "unknown"
