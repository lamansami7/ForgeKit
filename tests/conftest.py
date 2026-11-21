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
