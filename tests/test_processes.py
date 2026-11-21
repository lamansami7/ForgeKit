"""Process tests."""

from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.system_service import get_processes

runner = CliRunner()


def test_processes_table():
    result = runner.invoke(app, ["system", "processes"])
    assert result.exit_code == 0


def test_processes_json():
    result = runner.invoke(app, ["system", "processes", "--json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert isinstance(data, list)


def test_get_processes_unit():
    procs = get_processes(limit=5)
    assert len(procs) <= 5
    for p in procs:
        assert p.pid > 0
        assert p.name


def test_processes_sort_memory():
    result = runner.invoke(app, ["system", "processes", "--sort", "memory"])
    assert result.exit_code == 0


def test_processes_invalid_sort():
    result = runner.invoke(app, ["system", "processes", "--sort", "invalid"])
    assert result.exit_code != 0
