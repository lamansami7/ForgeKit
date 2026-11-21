"""Security tests."""

from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.security_service import check_security, scan_risky_config

runner = CliRunner()


def test_check_security(tmp_path):
    findings = check_security(tmp_path)
    assert isinstance(findings, list)
    assert len(findings) >= 3


def test_scan_risky_config(tmp_path):
    f = tmp_path / "config.ini"
    f.write_text("password = supersecret123\n")
    findings = scan_risky_config(f)
    assert len(findings) >= 1
    assert any("password" in fl["message"].lower() for fl in findings)


def test_scan_clean_file(tmp_path):
    f = tmp_path / "clean.txt"
    f.write_text("hello world\n")
    findings = scan_risky_config(f)
    assert len(findings) == 0


def test_security_cli(tmp_path):
    result = runner.invoke(app, ["security", "--path", str(tmp_path)])
    assert result.exit_code == 0


def test_security_json(tmp_path):
    result = runner.invoke(app, ["security", "--path", str(tmp_path), "--json"])
    assert result.exit_code == 0
    import json

    json.loads(result.output)


def test_security_check_cli(tmp_path):
    result = runner.invoke(app, ["security", "check", "--path", str(tmp_path)])
    assert result.exit_code == 0


def test_security_scan_cli(tmp_path):
    f = tmp_path / "test.conf"
    f.write_text("PermitRootLogin yes\n")
    result = runner.invoke(app, ["security", "scan", str(f)])
    assert result.exit_code == 0
