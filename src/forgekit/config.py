"""Configuration management."""

from __future__ import annotations

import math
import os
import tempfile
import tomllib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import tomlkit

from forgekit.constants import (
    DEFAULT_DASHBOARD_REFRESH,
    DISK_WARNING_THRESHOLD,
)
from forgekit.exceptions import ConfigError

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
        p = resolve_config_path(path)
        if not p.exists() and not p.is_symlink():
            return cls()
        if p.is_symlink():
            raise ConfigError(f"Refusing symbolic-link configuration file: {p}")
        try:
            with p.open("rb") as stream:
                data = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"Cannot read configuration {p}: {exc}") from exc
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ForgeConfig:
        cfg = cls()
        defaults = cfg.to_dict()
        for section, values in data.items():
            if section not in defaults:
                raise ConfigError(f"Unknown configuration section: {section}")
            if not isinstance(values, dict):
                raise ConfigError(f"Configuration section {section} must be a table")
            for key, value in values.items():
                if key not in defaults[section]:
                    raise ConfigError(f"Unknown configuration key: {section}.{key}")
                expected = defaults[section][key]
                valid_type = (
                    isinstance(value, type(expected))
                    if not isinstance(expected, float)
                    else isinstance(value, (int, float)) and not isinstance(value, bool)
                )
                if (
                    isinstance(expected, int)
                    and not isinstance(expected, bool)
                    and isinstance(value, bool)
                ):
                    valid_type = False
                if not valid_type:
                    raise ConfigError(
                        f"Invalid type for {section}.{key}; expected {type(expected).__name__}"
                    )
                setattr(
                    getattr(cfg, section),
                    key,
                    float(value) if isinstance(expected, float) else value,
                )
        return cfg

    def to_dict(self) -> dict[str, Any]:
        return {
            section: asdict(getattr(self, section))
            for section in ("general", "dashboard", "thresholds", "backup", "files", "network")
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.general.output_format not in ("auto", "table", "json", "plain"):
            errors.append(f"Invalid general.output_format: {self.general.output_format}")
        if self.general.log_level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            errors.append("general.log_level must be DEBUG, INFO, WARNING, ERROR or CRITICAL")
        if (
            not math.isfinite(self.dashboard.refresh_interval)
            or not 0.5 <= self.dashboard.refresh_interval <= 60
        ):
            errors.append("dashboard.refresh_interval must be between 0.5 and 60")
        for key in ("cpu_warning", "memory_warning", "disk_warning"):
            value = getattr(self.thresholds, key)
            if not math.isfinite(value) or not 0 < value <= 100:
                errors.append(f"thresholds.{key} must be between 0 and 100")
        if self.backup.compression not in ("gz", "bz2", "xz", "none"):
            errors.append("backup.compression must be one of gz, bz2, xz, none")
        if not self.backup.default_destination:
            errors.append("backup.default_destination must not be empty")
        if self.files.large_threshold_mb < 0:
            errors.append("files.large_threshold_mb must be non-negative")
        if not all(isinstance(item, str) and item for item in self.files.exclude_dirs):
            errors.append("files.exclude_dirs must contain non-empty strings")
        for key in ("ping_timeout", "http_timeout"):
            if not 1 <= getattr(self.network, key) <= 60:
                errors.append(f"network.{key} must be between 1 and 60")
        return errors

    def save(self, path: Path | None = None) -> Path:
        p = resolve_config_path(path)
        errors = self.validate()
        if errors:
            raise ConfigError("Invalid configuration: " + "; ".join(errors))
        try:
            if p.is_symlink():
                raise ConfigError(f"Refusing symbolic-link configuration file: {p}")
            # Preserve comments and existing TOML formatting, never discard user keys.
            document = (
                tomlkit.parse(p.read_text(encoding="utf-8")) if p.exists() else tomlkit.document()
            )
            for section, values in self.to_dict().items():
                if section not in document:
                    document[section] = tomlkit.table()
                for key, value in values.items():
                    document[section][key] = value
            _atomic_write(p, tomlkit.dumps(document), overwrite=True)
        except (OSError, ValueError, tomlkit.exceptions.ParseError) as exc:
            raise ConfigError(f"Cannot save configuration {p}: {exc}") from exc
        return p


def default_config_file() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    # The XDG specification requires an absolute path; ignore relative values.
    directory = Path(base) if base and Path(base).is_absolute() else Path.home() / ".config"
    return directory / "forgekit" / "config.toml"


def resolve_config_path(path: Path | str | None = None) -> Path:
    if path is not None:
        return Path(path).expanduser()
    return default_config_file()


def _atomic_write(path: Path, content: str, overwrite: bool) -> None:
    if path.is_symlink():
        raise ConfigError(f"Refusing symbolic-link configuration file: {path}")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if overwrite:
            os.replace(temp, path)
        else:
            os.link(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def get_config(path: Path | None = None) -> ForgeConfig:
    cfg = ForgeConfig.load(path)
    errors = cfg.validate()
    if errors:
        raise ConfigError("Invalid configuration: " + "; ".join(errors))
    return cfg


def ensure_default_config(path: Path | None = None, overwrite: bool = False) -> Path:
    p = resolve_config_path(path)
    exists = f"Configuration already exists: {p}; pass --force to replace it"
    if not overwrite and p.exists() and not p.is_symlink():
        raise ConfigError(exists)
    try:
        _atomic_write(p, DEFAULT_CONFIG_TOML, overwrite)
    except FileExistsError as exc:
        # Another process created the file between the check and publication.
        raise ConfigError(exists) from exc
    except OSError as exc:
        raise ConfigError(f"Cannot create configuration {p}: {exc}") from exc
    return p
