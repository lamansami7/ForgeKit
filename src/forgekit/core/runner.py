"""Runner — shared execution context."""

from dataclasses import dataclass
from pathlib import Path

from forgekit.config import ForgeConfig, get_config
from forgekit.platform import PlatformInfo, get_platform_info


@dataclass
class RunnerContext:
    config: ForgeConfig
    platform: PlatformInfo
    json_output: bool = False
    verbose: bool = False
    config_path: Path | None = None

    @classmethod
    def create(
        cls, json_output: bool = False, verbose: bool = False, config_path: Path | None = None
    ) -> "RunnerContext":
        cfg = get_config(config_path)
        plat = get_platform_info()
        return cls(
            config=cfg,
            platform=plat,
            json_output=json_output,
            verbose=verbose,
            config_path=config_path,
        )
