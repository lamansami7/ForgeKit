"""Ports tests."""

from typer.testing import CliRunner

from forgekit.cli import app

runner = CliRunner()


def test_ports_command():
    result = runner.invoke(app, ["net", "ports"])
    assert result.exit_code == 0


def test_ports_json():
    result = runner.invoke(app, ["net", "ports", "--json"])
    assert result.exit_code == 0
    import json

    json.loads(result.output)
