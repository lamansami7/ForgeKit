"""Test system diagnostics."""

from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.system_service import (
    get_cpu_info,
    get_disk_info,
    get_memory_info,
    get_system_summary,
)

runner = CliRunner()


def test_cpu_json():
    result = runner.invoke(app, ["system", "cpu", "--json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert "model" in data
    assert "logical_cores" in data


def test_cpu_table():
    result = runner.invoke(app, ["system", "cpu"])
    assert result.exit_code == 0
    assert "CPU" in result.output


def test_memory_json():
    result = runner.invoke(app, ["system", "memory", "--json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert "total" in data
    assert "percent" in data


def test_disk_json():
    result = runner.invoke(app, ["system", "disk", "--json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert "partitions" in data


def test_system_summary_json():
    result = runner.invoke(app, ["system", "--json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert "hostname" in data
    assert "python_version" in data


def test_system_summary_table():
    result = runner.invoke(app, ["system"])
    assert result.exit_code == 0
    assert "System Summary" in result.output or "Host" in result.output


def test_get_cpu_info_unit():
    info = get_cpu_info()
    assert info.logical_cores >= 1
    assert info.physical_cores >= 1


def test_get_memory_info_unit():
    info = get_memory_info()
    assert info.total > 0
    assert 0 <= info.percent <= 100


def test_get_disk_info_unit():
    info = get_disk_info()
    assert isinstance(info.partitions, list)


def test_system_summary_unit():
    s = get_system_summary()
    assert s.hostname
    assert s.python_version
