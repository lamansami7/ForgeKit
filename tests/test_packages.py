"""Packages tests."""

from unittest.mock import patch

from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.package_service import detect_managers

runner = CliRunner()


def test_detect_managers():
    managers = detect_managers()
    assert isinstance(managers, list)


def test_packages_cli():
    result = runner.invoke(app, ["packages"])
    assert result.exit_code == 0


def test_packages_json():
    result = runner.invoke(app, ["packages", "--json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert "managers" in data


def test_packages_list_mock():
    with patch(
        "forgekit.commands.packages.list_installed_packages",
        return_value=["pkg1 1.0", "pkg2 2.0"],
    ):
        result = runner.invoke(app, ["packages", "list", "--manager", "apt"])
        assert result.exit_code == 0
        assert "pkg1" in result.output


def test_packages_updates_mock():
    with patch(
        "forgekit.commands.packages.check_updates_generic",
        return_value={
            "manager": "apt",
            "available": True,
            "upgradable_count": 2,
            "upgradable": ["pkg1"],
        },
    ):
        result = runner.invoke(app, ["packages", "updates", "--manager", "apt"])
        assert result.exit_code == 0
        assert "Upgradable: 2" in result.output
