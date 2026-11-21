"""Developer tests."""

from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.developer_service import detect_all, path_diagnostics

runner = CliRunner()


def test_detect_all():
    tools = detect_all()
    assert isinstance(tools, list)
    assert len(tools) > 10
    # python should be found
    py = [t for t in tools if t["name"] == "python"]
    assert py[0]["found"] is True


def test_path_diagnostics():
    issues = path_diagnostics()
    assert isinstance(issues, list)
    assert len(issues) >= 1


def test_dev_cli():
    result = runner.invoke(app, ["dev"])
    assert result.exit_code == 0


def test_dev_json():
    result = runner.invoke(app, ["dev", "--json"])
    assert result.exit_code == 0
    import json

    json.loads(result.output)


def test_dev_versions():
    result = runner.invoke(app, ["dev", "versions"])
    assert result.exit_code == 0


def test_dev_check():
    result = runner.invoke(app, ["dev", "check"])
    assert result.exit_code == 0
