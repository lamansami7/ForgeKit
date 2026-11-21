"""System information services."""

import contextlib
import os
import platform
import time
from pathlib import Path

import psutil

from forgekit.models.system_info import (
    CpuInfo,
    DiskInfo,
    DiskPartitionInfo,
    MemoryInfo,
    ProcessInfo,
    SystemSummary,
)
from forgekit.platform import get_current_user, get_hostname


def get_cpu_info() -> CpuInfo:
    # CPU model
    model = platform.processor() or platform.machine() or "Unknown"
    # Try /proc/cpuinfo on Linux for better model name
    if Path("/proc/cpuinfo").exists():
        try:
            text = Path("/proc/cpuinfo").read_text()
            for line in text.splitlines():
                if line.startswith("model name"):
                    model = line.split(":", 1)[1].strip()
                    break
        except Exception:
            pass

    physical = psutil.cpu_count(logical=False) or 1
    logical = psutil.cpu_count(logical=True) or 1
    usage = psutil.cpu_percent(interval=0.5)
    per_core = psutil.cpu_percent(interval=0.3, percpu=True) or []

    freq = None
    freq_current = None
    freq_min = None
    freq_max = None
    try:
        freq = psutil.cpu_freq()
        if freq:
            freq_current = freq.current
            freq_min = freq.min
            freq_max = freq.max
    except Exception:
        pass

    return CpuInfo(
        model=model,
        architecture=platform.machine(),
        physical_cores=physical,
        logical_cores=logical,
        usage_percent=round(usage, 1),
        per_core_percent=[round(x, 1) for x in per_core],
        frequency_current_mhz=freq_current,
        frequency_min_mhz=freq_min,
        frequency_max_mhz=freq_max,
    )


def get_memory_info() -> MemoryInfo:
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()
    return MemoryInfo(
        total=vm.total,
        available=vm.available,
        used=vm.used,
        free=vm.free,
        percent=vm.percent,
        swap_total=swap.total,
        swap_used=swap.used,
        swap_free=swap.free,
        swap_percent=swap.percent,
        swap_sin=getattr(swap, "sin", None),
        swap_sout=getattr(swap, "sout", None),
    )


def get_disk_info() -> DiskInfo:
    partitions = []
    try:
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append(
                    DiskPartitionInfo(
                        device=part.device,
                        mountpoint=part.mountpoint,
                        fstype=part.fstype,
                        total=usage.total,
                        used=usage.used,
                        free=usage.free,
                        percent=usage.percent,
                    )
                )
            except (PermissionError, FileNotFoundError, OSError):
                continue
    except Exception:
        pass
    return DiskInfo(partitions=partitions)


def get_processes(limit: int = 10, sort_by: str = "cpu") -> list[ProcessInfo]:
    procs: list[ProcessInfo] = []
    for p in psutil.process_iter(
        [
            "pid",
            "name",
            "username",
            "cpu_percent",
            "memory_percent",
            "memory_info",
            "status",
            "create_time",
        ]
    ):
        try:
            info = p.info
            mem_info = info.get("memory_info")
            rss = mem_info.rss if mem_info else 0
            procs.append(
                ProcessInfo(
                    pid=info["pid"],
                    name=info.get("name") or "unknown",
                    username=info.get("username"),
                    cpu_percent=info.get("cpu_percent") or 0.0,
                    memory_percent=info.get("memory_percent") or 0.0,
                    memory_rss=rss,
                    status=info.get("status") or "unknown",
                    create_time=info.get("create_time"),
                )
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    # CPU percent needs previous call; trigger measurement
    # Already have cpu_percent but may be 0.0 if first call; sort anyway
    if sort_by == "memory":
        procs.sort(key=lambda x: x.memory_percent, reverse=True)
    else:
        procs.sort(key=lambda x: x.cpu_percent, reverse=True)
    return procs[:limit]


def get_uptime() -> float:
    try:
        return time.time() - psutil.boot_time()
    except Exception:
        return 0.0


def get_load_avg() -> tuple[float, float, float] | None:
    try:
        return os.getloadavg()  # type: ignore
    except Exception:
        return None


def get_battery() -> tuple[float | None, bool | None]:
    try:
        b = psutil.sensors_battery()
        if b:
            return b.percent, b.power_plugged
    except Exception:
        pass
    return None, None


def get_system_summary() -> SystemSummary:
    cpu = None
    memory = None
    disk = None
    with contextlib.suppress(Exception):
        cpu = get_cpu_info()
    with contextlib.suppress(Exception):
        memory = get_memory_info()
    with contextlib.suppress(Exception):
        disk = get_disk_info()

    battery_pct, battery_plugged = get_battery()

    return SystemSummary(
        hostname=get_hostname(),
        os_name=platform.system(),
        os_version=platform.version(),
        kernel=platform.release(),
        architecture=platform.machine(),
        uptime_seconds=get_uptime(),
        cpu=cpu,
        memory=memory,
        disk=disk,
        python_version=platform.python_version(),
        user=get_current_user(),
        load_avg=get_load_avg(),
        battery_percent=battery_pct,
        battery_plugged=battery_plugged,
    )
