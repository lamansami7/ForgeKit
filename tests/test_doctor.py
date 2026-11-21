"""Doctor tests."""

from typer.testing import CliRunner

from forgekit.cli import app

runner = CliRunner()


def test_doctor():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1)  # allow warnings
    assert "ForgeKit Doctor" in result.output or "Python version" in result.output


def test_doctor_json():
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code in (0, 1)
    import json

    data = json.loads(result.output)
    assert isinstance(data, list)
    assert any("Python version" in d["name"] for d in data)


def test_doctor_verbose():
    result = runner.invoke(app, ["doctor", "--verbose"])
    assert result.exit_code in (0, 1)
