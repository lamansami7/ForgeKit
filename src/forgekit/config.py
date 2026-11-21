"""Configuration management."""

from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomli_w  # type: ignore

    HAS_TOMLI_W = True
except ImportError:
    HAS_TOMLI_W = False

from forgekit.constants import (
    DEFAULT_CONFIG_FILE,
    DEFAULT_DASHBOARD_REFRESH,
    DISK_WARNING_THRESHOLD,
)

DEFAULT_CONFIG_TOML = """# ForgeKit Configuration
# Location: ~/.config/forgekit/config.toml

[general]
# Output format: auto, table, json, plain
output_format = "auto"
colors = true
log_level = "WARNING"

[dashboard]
refresh_interval = 2.0
show_network = true
show_processes = true

[thresholds]
cpu_warning = 80.0
memory_warning = 85.0
disk_warning = 85.0

[backup]
default_destination = "~/backups"
compression = "gz"

[files]
large_threshold_mb = 100
exclude_dirs = [".git", "__pycache__", ".venv", "venv", "node_modules", ".cache"]

[network]
ping_timeout = 5
http_timeout = 10
"""


@dataclass
class GeneralConfig:
    output_format: str = "auto"
    colors: bool = True
    log_level: str = "WARNING"


@dataclass
class DashboardConfig:
    refresh_interval: float = DEFAULT_DASHBOARD_REFRESH
    show_network: bool = True
    show_processes: bool = True


@dataclass
class ThresholdsConfig:
    cpu_warning: float = 80.0
    memory_warning: float = 85.0
    disk_warning: float = DISK_WARNING_THRESHOLD


@dataclass
class BackupConfig:
    default_destination: str = "~/backups"
    compression: str = "gz"


@dataclass
class FilesConfig:
    large_threshold_mb: int = 100
    exclude_dirs: list[str] = field(
        default_factory=lambda: [".git", "__pycache__", ".venv", "venv", "node_modules", ".cache"]
    )


@dataclass
class NetworkConfig:
    ping_timeout: int = 5
    http_timeout: int = 10


@dataclass
class ForgeConfig:
    general: GeneralConfig = field(default_factory=GeneralConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    backup: BackupConfig = field(default_factory=BackupConfig)
    files: FilesConfig = field(default_factory=FilesConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)

    @classmethod
    def load(cls, path: Path | None = None) -> ForgeConfig:
        p = path or DEFAULT_CONFIG_FILE
        if not p.exists():
            return cls()
        try:
            with open(p, "rb") as f:
                data = tomllib.load(f)
        except Exception:
            return cls()
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ForgeConfig:
        cfg = cls()
        if "general" in data:
            g = data["general"]
            cfg.general.output_format = g.get("output_format", cfg.general.output_format)
            cfg.general.colors = g.get("colors", cfg.general.colors)
            cfg.general.log_level = g.get("log_level", cfg.general.log_level)
        if "dashboard" in data:
            d = data["dashboard"]
            cfg.dashboard.refresh_interval = float(
                d.get("refresh_interval", cfg.dashboard.refresh_interval)
            )
            cfg.dashboard.show_network = d.get("show_network", cfg.dashboard.show_network)
            cfg.dashboard.show_processes = d.get("show_processes", cfg.dashboard.show_processes)
        if "thresholds" in data:
            t = data["thresholds"]
            cfg.thresholds.cpu_warning = float(t.get("cpu_warning", cfg.thresholds.cpu_warning))
            cfg.thresholds.memory_warning = float(
                t.get("memory_warning", cfg.thresholds.memory_warning)
            )
            cfg.thresholds.disk_warning = float(t.get("disk_warning", cfg.thresholds.disk_warning))
        if "backup" in data:
            b = data["backup"]
            cfg.backup.default_destination = b.get(
                "default_destination", cfg.backup.default_destination
            )
            cfg.backup.compression = b.get("compression", cfg.backup.compression)
        if "files" in data:
            f = data["files"]
            cfg.files.large_threshold_mb = int(
                f.get("large_threshold_mb", cfg.files.large_threshold_mb)
            )
            cfg.files.exclude_dirs = f.get("exclude_dirs", cfg.files.exclude_dirs)
        if "network" in data:
            n = data["network"]
            cfg.network.ping_timeout = int(n.get("ping_timeout", cfg.network.ping_timeout))
            cfg.network.http_timeout = int(n.get("http_timeout", cfg.network.http_timeout))
        return cfg

    def to_dict(self) -> dict[str, Any]:
        return {
            "general": asdict(self.general),
            "dashboard": asdict(self.dashboard),
            "thresholds": asdict(self.thresholds),
            "backup": asdict(self.backup),
            "files": asdict(self.files),
            "network": asdict(self.network),
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.general.output_format not in ("auto", "table", "json", "plain"):
            errors.append(f"Invalid output_format: {self.general.output_format}")
        if not (0.5 <= self.dashboard.refresh_interval <= 60):
            errors.append("dashboard.refresh_interval must be between 0.5 and 60")
        for k in ("cpu_warning", "memory_warning", "disk_warning"):
            v = getattr(self.thresholds, k)
            if not (0 < v <= 100):
                errors.append(f"thresholds.{k} must be between 0 and 100")
        if self.backup.compression not in ("gz", "bz2", "xz", "none"):
            errors.append("backup.compression must be one of gz, bz2, xz, none")
        return errors

    def save(self, path: Path | None = None) -> Path:
        p = path or DEFAULT_CONFIG_FILE
        p.parent.mkdir(parents=True, exist_ok=True)
        if HAS_TOMLI_W:
            with open(p, "wb") as f:
                tomli_w.dump(self.to_dict(), f)
        else:
            # Fallback manual TOML writing
            content = self._to_toml_string()
            p.write_text(content)
        return p

    def _to_toml_string(self) -> str:
        lines: list[str] = []
        d = self.to_dict()
        for section, values in d.items():
            lines.append(f"[{section}]")
            for k, v in values.items():
                if isinstance(v, str):
                    lines.append(f'{k} = "{v}"')
                elif isinstance(v, bool):
                    lines.append(f"{k} = {'true' if v else 'false'}")
                elif isinstance(v, list):
                    items = ", ".join(f'"{x}"' for x in v)
                    lines.append(f"{k} = [{items}]")
                else:
                    lines.append(f"{k} = {v}")
            lines.append("")
        return "\n".join(lines)


def get_config(path: Path | None = None) -> ForgeConfig:
    return ForgeConfig.load(path)


def ensure_default_config() -> Path:
    p = DEFAULT_CONFIG_FILE
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(DEFAULT_CONFIG_TOML)
    return p
