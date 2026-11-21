"""Network models."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class PingResult:
    host: str
    resolved_ip: str | None
    packets_sent: int
    packets_received: int
    packet_loss_percent: float
    rtts: list[float]  # ms
    avg_ms: float | None
    min_ms: float | None
    max_ms: float | None
    success: bool
    error: str | None = None
    method: str = "icmp"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DnsResult:
    domain: str
    ipv4: list[str]
    ipv6: list[str]
    cname: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HttpResult:
    url: str
    status_code: int | None
    reason: str | None
    elapsed_ms: float
    final_url: str | None
    redirected: bool
    tls_version: str | None = None
    headers: dict[str, str] | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PortInfo:
    proto: str
    local_addr: str
    local_port: int
    state: str
    pid: int | None
    process: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InterfaceInfo:
    name: str
    is_up: bool | None
    mtu: int | None
    ipv4: list[str]
    ipv6: list[str]
    mac: str | None
    bytes_sent: int | None
    bytes_recv: int | None
    packets_sent: int | None
    packets_recv: int | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConnectivityCheck:
    name: str
    success: bool
    latency_ms: float | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
