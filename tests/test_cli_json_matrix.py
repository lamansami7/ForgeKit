"""CLI-level output and failure contracts for representative commands."""

import json

from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.models.network_info import ConnectivityCheck, DnsResult, HttpResult, PingResult

runner = CliRunner()


def test_network_command_json_and_exit_codes(monkeypatch):
    monkeypatch.setattr(
        "forgekit.commands.network.ping_host",
        lambda *a, **k: PingResult(
            host="example.test",
            resolved_ip="192.0.2.1",
            packets_sent=1,
            packets_received=1,
            packet_loss_percent=0.0,
            rtts=[1.0],
            avg_ms=1.0,
            min_ms=1.0,
            max_ms=1.0,
            success=True,
            method="icmp",
        ),
    )
    monkeypatch.setattr(
        "forgekit.commands.network.resolve_dns",
        lambda host: DnsResult(domain=host, ipv4=["192.0.2.1"], ipv6=[]),
    )
    monkeypatch.setattr(
        "forgekit.commands.network.check_http",
        lambda *a, **k: HttpResult(
            url="https://example.test",
            status_code=200,
            reason="OK",
            elapsed_ms=1.0,
            final_url=None,
            redirected=False,
            headers={"Content-Type": "text/plain"},
        ),
    )
    for args, field, expected in [
        (["net", "ping", "example.test", "--json"], "success", True),
        (["net", "dns", "example.test", "--json"], "ipv4", ["192.0.2.1"]),
        (["net", "http", "https://example.test", "--json"], "status_code", 200),
    ]:
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
        assert json.loads(result.output)[field] == expected
        assert "\x1b[" not in result.output
    monkeypatch.setattr(
        "forgekit.commands.network.check_connectivity",
        lambda timeout: [
            ConnectivityCheck(name="dns", success=True, latency_ms=1.0),
            ConnectivityCheck(name="https", success=False, latency_ms=None, error="timeout"),
        ],
    )
    result = runner.invoke(app, ["net", "check", "--json"])
    assert result.exit_code == 1
    assert [item["success"] for item in json.loads(result.output)] == [True, False]


def test_global_json_errors_remain_parseable_for_expected_failures(tmp_path):
    for args in [
        ["system", "processes", "--sort", "bad"],
        ["files", "size", str(tmp_path / "missing")],
        ["git", "branches", "--path", str(tmp_path)],
        ["security", "scan", str(tmp_path / "missing")],
        ["workspace", "inspect", str(tmp_path / "missing")],
        ["dashboard", "--refresh", "100"],
    ]:
        result = runner.invoke(app, ["--json", *args])
        assert result.exit_code == 1, (args, result.output, result.exception)
        assert "error" in json.loads(result.output)


def test_all_command_group_help_pages():
    for name in (
        "system",
        "net",
        "git",
        "files",
        "packages",
        "dev",
        "security",
        "backup",
        "workspace",
        "doctor",
        "dashboard",
        "config",
        "info",
    ):
        result = runner.invoke(app, [name, "--help"])
        assert result.exit_code == 0, (name, result.output)
        assert "Usage:" in result.output


def test_dashboard_rejects_non_finite_refresh_as_json():
    result = runner.invoke(app, ["dashboard", "--refresh", "nan", "--json"])
    assert result.exit_code == 1
    assert "error" in json.loads(result.output)


def test_explicit_json_syntax_errors_at_any_level_and_normal_text(tmp_path):
    for args in [
        ["--json", "not-a-command"],
        ["--json", "--unknown"],
        ["net", "ping", "--json"],
        ["system", "processes", "--limit", "0", "--json"],
        ["backup", "restore", "--json"],
    ]:
        result = runner.invoke(app, args)
        assert result.exit_code == 2, (args, result.output, result.exception)
        assert isinstance(json.loads(result.stdout)["error"], str)
        assert result.stderr == ""
    result = runner.invoke(app, ["net", "ping"])
    assert result.exit_code == 2
    assert "Usage:" in result.output


def test_leaf_json_flag_covers_early_config_error_and_config_driven_parser_error(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("[invalid\n")
    result = runner.invoke(app, ["--config", str(bad), "net", "ping", "localhost", "--json"])
    assert result.exit_code == 1
    assert "configuration" in json.loads(result.stdout)["error"].lower()
    assert result.stderr == ""

    configured = tmp_path / "json.toml"
    configured.write_text('[general]\noutput_format = "json"\n')
    result = runner.invoke(app, ["--config", str(configured), "net", "ping"])
    assert result.exit_code == 2
    assert "error" in json.loads(result.stdout)
    assert result.stderr == ""


def test_double_dash_json_is_a_positional_argument(tmp_path):
    (tmp_path / "--json").write_text("match")
    result = runner.invoke(app, ["files", "search", str(tmp_path), "--", "--json"])
    assert result.exit_code == 0, (result.output, result.exception)
    assert "--json" in result.output
    # A subsequent invocation must not inherit explicit JSON mode.
    missing = runner.invoke(app, ["net", "ping"])
    assert missing.exit_code == 2 and "Usage:" in missing.output


def test_explicit_json_abort_has_a_clean_error_and_nonzero_exit(monkeypatch):
    import typer

    def abort(*args, **kwargs):
        raise typer.Abort()

    monkeypatch.setattr("forgekit.commands.network.ping_host", abort)
    result = runner.invoke(app, ["net", "ping", "localhost", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout) == {"error": "Aborted"}
    assert result.stderr == ""
