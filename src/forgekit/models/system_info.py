"""System info models."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class CpuInfo:
    model: str
    architecture: str
    physical_cores: int | None
    logical_cores: int | None
    usage_percent: float
    per_core_percent: list[float]
    frequency_current_mhz: float | None
    frequency_min_mhz: float | None
    frequency_max_mhz: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MemoryInfo:
    total: int
    available: int
    used: int
    free: int
    percent: float
    swap_total: int
    swap_used: int
    swap_free: int
    swap_percent: float
    swap_sin: int | None = None
    swap_sout: int | None = None
    raw_used: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiskPartitionInfo:
    device: str
    mountpoint: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiskInfo:
    partitions: list[DiskPartitionInfo]

    def to_dict(self) -> dict[str, Any]:
        return {"partitions": [p.to_dict() for p in self.partitions]}


@dataclass
class ProcessInfo:
    pid: int
    name: str
    username: str | None
    cpu_percent: float | None
    memory_percent: float | None
    memory_rss: int | None
    status: str
    create_time: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SystemSummary:
    hostname: str
    os_name: str
    os_version: str
    kernel: str
    architecture: str
    uptime_seconds: float | None
    cpu: CpuInfo | None
    memory: MemoryInfo | None
    disk: DiskInfo | None
    python_version: str
    user: str
    load_avg: tuple[float, float, float] | None = None
    battery_percent: float | None = None
    battery_plugged: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Handle cpu/memory/disk nested
        if self.cpu:
            d["cpu"] = self.cpu.to_dict()
        if self.memory:
            d["memory"] = self.memory.to_dict()
        if self.disk:
            d["disk"] = self.disk.to_dict()
        return d
