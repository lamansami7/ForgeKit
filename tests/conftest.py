"""Pytest conftest."""

from pathlib import Path

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def tmp_path_fixture(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def forge_runner():
    return CliRunner()


@pytest.fixture(autouse=True)
def isolate_user_configuration(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep user configuration isolated from both real home and test data trees."""
    home = tmp_path_factory.mktemp("forge-home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "xdg-config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(home / "xdg-cache"))
