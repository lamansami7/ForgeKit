"""Test CLI basics."""

from typer.testing import CliRunner

from forgekit.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "forge" in result.output.lower() or "ForgeKit" in result.output


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output or "ForgeKit" in result.output


def test_root_no_args():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "ForgeKit" in result.output or "Available commands" in result.output


def test_unknown_command():
    result = runner.invoke(app, ["nonexistent"])
    assert result.exit_code != 0


def test_system_help():
    result = runner.invoke(app, ["system", "--help"])
    assert result.exit_code == 0


def test_net_help():
    result = runner.invoke(app, ["net", "--help"])
    assert result.exit_code == 0


def test_git_help():
    result = runner.invoke(app, ["git", "--help"])
    assert result.exit_code == 0
