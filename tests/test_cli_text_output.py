"""Human-readable rendering for every command (the text path users actually see)."""

import json
import os
import subprocess

import pytest
from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.models.network_info import (
    ConnectivityCheck,
    DnsResult,
    HttpResult,
    InterfaceInfo,
    PingResult,
    PortInfo,
)

runner = CliRunner()


@pytest.fixture()
def repo(tmp_path):
    path = tmp_path / "repo"
    path.mkdir()
    env = os.environ | {
        "GIT_AUTHOR_NAME": "Tester",
        "GIT_AUTHOR_EMAIL": "tester@example.test",
        "GIT_COMMITTER_NAME": "Tester",
        "GIT_COMMITTER_EMAIL": "tester@example.test",
    }
    subprocess.run(["git", "init", "-q", str(path)], check=True, env=env)
    (path / "tracked.txt").write_text("content")
    subprocess.run(["git", "add", "tracked.txt"], check=True, cwd=path, env=env)
    subprocess.run(["git", "commit", "-qm", "initial commit"], check=True, cwd=path, env=env)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://user:token@example.test/repo.git"],
        check=True,
        cwd=path,
        env=env,
    )
    return path


# --- root and system -------------------------------------------------------


def test_root_index_lists_commands():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Available commands" in result.output
    assert "forge system cpu" in result.output


def test_system_summary_text():
    result = runner.invoke(app, ["system"])
    assert result.exit_code == 0
    assert "System Summary" in result.output
    assert "Uptime" in result.output


def test_system_cpu_text_with_per_core():
    result = runner.invoke(app, ["system", "cpu", "--per-core"])
    assert result.exit_code == 0
    assert "CPU Information" in result.output
    assert "Logical processors" in result.output
    assert "Core 0" in result.output


def test_system_memory_text():
    result = runner.invoke(app, ["system", "memory"])
    assert result.exit_code == 0
    assert "RAM" in result.output
    assert "Swap" in result.output


def test_system_disk_text():
    result = runner.invoke(app, ["system", "disk"])
    assert result.exit_code == 0
    assert "Disk Usage" in result.output or "No disk partitions" in result.output


def test_system_processes_text_both_sorts():
    for sort in ("cpu", "memory"):
        result = runner.invoke(app, ["system", "processes", "--sort", sort, "--limit", "3"])
        assert result.exit_code == 0
        assert "Processes by" in result.output
        assert "never terminates processes" in result.output


# --- network ---------------------------------------------------------------


def test_net_overview_text():
    result = runner.invoke(app, ["net"])
    assert result.exit_code == 0
    assert "Interfaces:" in result.output
    assert "forge net ports" in result.output


def test_net_ping_text_success(monkeypatch):
    monkeypatch.setattr(
        "forgekit.commands.network.ping_host",
        lambda *a, **k: PingResult(
            host="example.test",
            resolved_ip="192.0.2.1",
            packets_sent=2,
            packets_received=2,
            packet_loss_percent=0.0,
            rtts=[1.2, 2.4],
            avg_ms=1.8,
            min_ms=1.2,
            max_ms=2.4,
            success=True,
            method="icmp",
        ),
    )
    result = runner.invoke(app, ["net", "ping", "example.test"])
    assert result.exit_code == 0
    assert "Host is reachable" in result.output
    assert "ICMP" in result.output


def test_net_ping_text_failure(monkeypatch):
    monkeypatch.setattr(
        "forgekit.commands.network.ping_host",
        lambda *a, **k: PingResult(
            host="example.test",
            resolved_ip="192.0.2.1",
            packets_sent=1,
            packets_received=0,
            packet_loss_percent=100.0,
            rtts=[],
            avg_ms=None,
            min_ms=None,
            max_ms=None,
            success=False,
            error="No ICMP reply received",
        ),
    )
    result = runner.invoke(app, ["net", "ping", "example.test"])
    assert result.exit_code == 1
    assert "No ICMP reply received" in result.output
    assert "192.0.2.1" in result.output


def test_net_dns_text_and_failure(monkeypatch):
    monkeypatch.setattr(
        "forgekit.commands.network.resolve_dns",
        lambda host, **kwargs: DnsResult(
            domain=host, ipv4=["192.0.2.1"], ipv6=["2001:db8::1"], cname="alias.test"
        ),
    )
    result = runner.invoke(app, ["net", "dns", "example.test", "--timeout", "3"])
    assert result.exit_code == 0
    assert "192.0.2.1" in result.output
    assert "CNAME" in result.output

    monkeypatch.setattr(
        "forgekit.commands.network.resolve_dns",
        lambda host, **kwargs: DnsResult(domain=host, ipv4=[], ipv6=[], error="NXDOMAIN"),
    )
    failed = runner.invoke(app, ["net", "dns", "nope.test"])
    assert failed.exit_code == 1
    assert "NXDOMAIN" in failed.output


def test_net_dns_text_without_records(monkeypatch):
    monkeypatch.setattr(
        "forgekit.commands.network.resolve_dns",
        lambda host, **kwargs: DnsResult(domain=host, ipv4=[], ipv6=[]),
    )
    result = runner.invoke(app, ["net", "dns", "empty.test"])
    assert result.exit_code == 0
    assert "none" in result.output


def test_net_check_text(monkeypatch):
    monkeypatch.setattr(
        "forgekit.commands.network.check_connectivity",
        lambda timeout: [
            ConnectivityCheck(name="dns", success=True, latency_ms=4.0),
            ConnectivityCheck(name="https", success=False, latency_ms=None, error="timeout"),
        ],
    )
    result = runner.invoke(app, ["net", "check"])
    assert result.exit_code == 1
    assert "OK" in result.output and "FAIL" in result.output
    assert "timeout" in result.output


def test_net_ports_text(monkeypatch):
    monkeypatch.setattr(
        "forgekit.commands.network.get_ports",
        lambda: [
            PortInfo(
                proto="tcp",
                local_addr="127.0.0.1",
                local_port=8080,
                state="LISTEN",
                pid=1,
                process="python",
            )
        ],
    )
    result = runner.invoke(app, ["net", "ports"])
    assert result.exit_code == 0
    assert "8080" in result.output


def test_net_ports_text_empty(monkeypatch):
    monkeypatch.setattr("forgekit.commands.network.get_ports", lambda: [])
    result = runner.invoke(app, ["net", "ports"])
    assert result.exit_code == 0
    assert "No listening ports" in result.output


def test_net_ports_text_error(monkeypatch):
    def explode():
        raise RuntimeError("permission denied")

    monkeypatch.setattr("forgekit.commands.network.get_ports", explode)
    result = runner.invoke(app, ["net", "ports"])
    assert result.exit_code == 1
    assert "permission denied" in result.output


def test_net_interfaces_text(monkeypatch):
    monkeypatch.setattr(
        "forgekit.commands.network.get_interfaces",
        lambda: [
            InterfaceInfo(
                name="eth0",
                is_up=True,
                mtu=1500,
                ipv4=["192.0.2.10"],
                ipv6=[],
                mac="aa:bb:cc:dd:ee:ff",
                bytes_sent=1024,
                bytes_recv=2048,
                packets_sent=10,
                packets_recv=20,
            )
        ],
    )
    result = runner.invoke(app, ["net", "interfaces"])
    assert result.exit_code == 0
    assert "eth0" in result.output
    assert "192.0.2.10" in result.output


def test_net_http_text(monkeypatch):
    monkeypatch.setattr(
        "forgekit.commands.network.check_http",
        lambda *a, **k: HttpResult(
            url="https://example.test",
            status_code=301,
            reason="Moved",
            elapsed_ms=5.0,
            final_url="https://example.test/final",
            redirected=True,
            headers={"content-type": "text/html", "set-cookie": "***redacted***"},
        ),
    )
    result = runner.invoke(app, ["net", "http", "example.test", "--headers"])
    assert result.exit_code == 0
    assert "Final URL" in result.output
    assert "Response Headers" in result.output


def test_net_http_text_failure(monkeypatch):
    monkeypatch.setattr(
        "forgekit.commands.network.check_http",
        lambda *a, **k: HttpResult(
            url="https://example.test",
            status_code=500,
            reason="Server Error",
            elapsed_ms=5.0,
            final_url=None,
            redirected=False,
        ),
    )
    result = runner.invoke(app, ["net", "http", "example.test"])
    assert result.exit_code == 1
    assert "500" in result.output


# --- git -------------------------------------------------------------------


def test_git_status_text_redacts_credentials(repo):
    result = runner.invoke(app, ["git", "status", "--path", str(repo)])
    assert result.exit_code == 0
    assert "Working Tree Status" in result.output
    assert "token" not in result.output
    assert "***@example.test" in result.output


def test_git_untracked_and_staged_rendering(repo):
    (repo / "new.txt").write_text("untracked")
    (repo / "tracked.txt").write_text("changed")
    result = runner.invoke(app, ["git", "--path", str(repo)])
    assert result.exit_code == 0
    assert "Untracked" in result.output
    assert "Unstaged" in result.output


def test_git_history_text(repo):
    result = runner.invoke(app, ["git", "history", "--path", str(repo), "--limit", "2"])
    assert result.exit_code == 0
    assert "initial commit" in result.output


def test_git_branches_text(repo):
    result = runner.invoke(app, ["git", "branches", "--path", str(repo)])
    assert result.exit_code == 0
    assert "Current branch" in result.output
    assert "Local Branches" in result.output


def test_git_inspect_text(repo):
    result = runner.invoke(app, ["git", "inspect", "tracked.txt", "--path", str(repo)])
    assert result.exit_code == 0
    assert "Inspect: tracked.txt" in result.output


def test_git_not_a_repo_text(tmp_path):
    result = runner.invoke(app, ["git", "status", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "Not a git repository" in result.output


# --- files -----------------------------------------------------------------


def test_files_large_text(tmp_path):
    (tmp_path / "big.bin").write_bytes(b"0" * (300 * 1024))
    result = runner.invoke(app, ["files", "large", str(tmp_path), "--threshold", "0"])
    assert result.exit_code == 0
    assert "Large Files" in result.output
    empty = runner.invoke(app, ["files", "large", str(tmp_path), "--threshold", "50"])
    assert empty.exit_code == 0
    assert "No files >=" in empty.output


def test_files_search_text(tmp_path):
    (tmp_path / "hello.txt").write_text("hello")
    result = runner.invoke(app, ["files", "search", str(tmp_path), "hello"])
    assert result.exit_code == 0
    assert "hello.txt" in result.output
    missing = runner.invoke(app, ["files", "search", str(tmp_path), "absent"])
    assert missing.exit_code == 0
    assert "No matches" in missing.output


def test_files_size_text(tmp_path):
    (tmp_path / "a.txt").write_text("hello world")
    (tmp_path / "sub").mkdir()
    result = runner.invoke(app, ["files", "size", str(tmp_path)])
    assert result.exit_code == 0
    assert "Total size" in result.output
    assert "Contents" in result.output


def test_files_empty_and_duplicates_text(tmp_path):
    (tmp_path / "empty").mkdir()
    (tmp_path / "a.txt").write_text("same")
    (tmp_path / "b.txt").write_text("same")
    empty = runner.invoke(app, ["files", "empty", str(tmp_path)])
    assert empty.exit_code == 0
    assert "Empty Directories" in empty.output
    dupes = runner.invoke(app, ["files", "duplicates", str(tmp_path)])
    assert dupes.exit_code == 0
    assert "Duplicate group" in dupes.output
    assert "No files were deleted" in dupes.output


def test_files_empty_none_text(tmp_path):
    (tmp_path / "a.txt").write_text("x")
    result = runner.invoke(app, ["files", "empty", str(tmp_path)])
    assert result.exit_code == 0
    assert "No empty directories" in result.output


# --- packages / developer --------------------------------------------------


def test_packages_text_with_managers(monkeypatch):
    monkeypatch.setattr(
        "forgekit.commands.packages.detect_managers",
        lambda: [
            {
                "name": "apt",
                "path": "/usr/bin/apt",
                "version": "apt 2.6",
                "update_cmd": "sudo apt update",
            }
        ],
    )
    result = runner.invoke(app, ["packages"])
    assert result.exit_code == 0
    assert "apt" in result.output
    assert "never auto-installs" in result.output


def test_packages_text_without_managers(monkeypatch):
    monkeypatch.setattr("forgekit.commands.packages.detect_managers", lambda: [])
    result = runner.invoke(app, ["packages"])
    assert result.exit_code == 0
    assert "No supported package managers" in result.output


def test_packages_list_text(monkeypatch):
    monkeypatch.setattr("forgekit.commands.packages.primary_manager", lambda: {"name": "apt"})
    monkeypatch.setattr(
        "forgekit.commands.packages.list_installed_packages",
        lambda manager, limit: ["pkg1 1.0", "pkg2 2.0"],
    )
    result = runner.invoke(app, ["packages", "list"])
    assert result.exit_code == 0
    assert "pkg1" in result.output


def test_packages_list_empty_and_error(monkeypatch):
    monkeypatch.setattr("forgekit.commands.packages.primary_manager", lambda: {"name": "apt"})
    monkeypatch.setattr(
        "forgekit.commands.packages.list_installed_packages", lambda manager, limit: []
    )
    empty = runner.invoke(app, ["packages", "list"])
    assert empty.exit_code == 0
    assert "no packages found" in empty.output

    def explode(manager, limit):
        raise RuntimeError("boom")

    monkeypatch.setattr("forgekit.commands.packages.list_installed_packages", explode)
    failed = runner.invoke(app, ["packages", "list"])
    assert failed.exit_code == 1
    assert "boom" in failed.output


def test_packages_updates_text(monkeypatch):
    monkeypatch.setattr("forgekit.commands.packages.primary_manager", lambda: {"name": "apt"})
    monkeypatch.setattr(
        "forgekit.commands.packages.check_updates_generic",
        lambda manager: {
            "manager": manager,
            "available": True,
            "upgradable_count": 2,
            "upgradable": ["a", "b"],
        },
    )
    result = runner.invoke(app, ["packages", "updates"])
    assert result.exit_code == 0
    assert "Upgradable: 2" in result.output


def test_packages_updates_text_no_metadata(monkeypatch):
    monkeypatch.setattr(
        "forgekit.commands.packages.primary_manager",
        lambda: {"name": "zypper", "update_cmd": "sudo zypper update"},
    )
    monkeypatch.setattr(
        "forgekit.commands.packages.check_updates_generic",
        lambda manager: {"manager": manager, "available": True, "note": "check manually"},
    )
    result = runner.invoke(app, ["packages", "updates"])
    assert result.exit_code == 0
    assert "check manually" in result.output


def test_packages_updates_unavailable(monkeypatch):
    monkeypatch.setattr("forgekit.commands.packages.primary_manager", lambda: {"name": "apt"})
    monkeypatch.setattr(
        "forgekit.commands.packages.check_updates_generic",
        lambda manager: {"manager": manager, "available": False, "error": "no metadata"},
    )
    result = runner.invoke(app, ["packages", "updates"])
    assert result.exit_code == 1
    assert "no metadata" in result.output


def test_dev_text_and_versions(monkeypatch):
    tools = [
        {"name": "python", "found": True, "version": "Python 3.11", "path": "/usr/bin/python3"},
        {"name": "ruby", "found": False, "version": None, "path": None, "details": "missing"},
    ]
    monkeypatch.setattr("forgekit.commands.developer.detect_all", lambda: tools)
    monkeypatch.setattr(
        "forgekit.commands.developer.path_diagnostics",
        lambda: [{"level": "pass", "message": "PATH looks sane", "fix": ""}],
    )
    result = runner.invoke(app, ["dev"])
    assert result.exit_code == 0
    assert "Developer Tools" in result.output
    assert "PATH Diagnostics" in result.output
    versions = runner.invoke(app, ["dev", "versions"])
    assert versions.exit_code == 0
    assert "Python 3.11" in versions.output
    assert "Missing: ruby" in versions.output


# --- security --------------------------------------------------------------


def test_security_text(monkeypatch):
    monkeypatch.setattr(
        "forgekit.commands.security.check_security",
        lambda path: [
            {"level": "warn", "check": "ssh_permissions", "message": "too open", "fix": "chmod"}
        ],
    )
    result = runner.invoke(app, ["security"])
    assert result.exit_code == 0
    assert "Security Findings" in result.output
    assert "does NOT claim a system is secure" in result.output


def test_security_text_error(monkeypatch):
    def explode(path):
        raise OSError("denied")

    monkeypatch.setattr("forgekit.commands.security.check_security", explode)
    result = runner.invoke(app, ["security"])
    assert result.exit_code == 1
    assert "denied" in result.output


def test_security_scan_text(monkeypatch, tmp_path):
    target = tmp_path / "app.conf"
    target.write_text("password = hunter2")
    monkeypatch.setattr(
        "forgekit.services.security_service.scan_risky_config",
        lambda path: [{"level": "warn", "check": "config_pattern", "message": "secret", "fix": ""}],
    )
    monkeypatch.setattr("forgekit.commands.security.check_security", lambda path: [])
    result = runner.invoke(app, ["security", "scan", str(target)])
    assert result.exit_code == 0
    assert "Scan:" in result.output

    monkeypatch.setattr("forgekit.services.security_service.scan_risky_config", lambda path: [])
    clean = runner.invoke(app, ["security", "scan", str(target)])
    assert clean.exit_code == 0
    assert "No risky patterns" in clean.output


# --- doctor / dashboard / info --------------------------------------------


def test_doctor_text_output():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1)
    assert "ForgeKit Doctor" in result.output


def test_doctor_text_verbose():
    result = runner.invoke(app, ["doctor", "--verbose"])
    assert result.exit_code in (0, 1)
    assert "Verbose:" in result.output


def test_dashboard_snapshot_when_redirected():
    result = runner.invoke(app, ["dashboard"])
    assert result.exit_code == 0
    assert "ForgeKit Dashboard" in result.output


def test_info_text():
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "ForgeKit Info" in result.output
    assert "MIT" in result.output


def test_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "ForgeKit version" in result.output


# --- config ----------------------------------------------------------------


def test_config_text_roundtrip(tmp_path):
    path = tmp_path / "config.toml"
    assert "Config created" in runner.invoke(app, ["config", "init", "--path", str(path)]).output
    shown = runner.invoke(app, ["config", "show", "--path", str(path)])
    assert shown.exit_code == 0
    assert "Configuration" in shown.output
    set_result = runner.invoke(
        app, ["config", "set", "dashboard.refresh_interval", "4", "--path", str(path)]
    )
    assert set_result.exit_code == 0
    assert "Set dashboard.refresh_interval = 4.0" in set_result.output
    got = runner.invoke(app, ["config", "get", "dashboard.refresh_interval", "--path", str(path)])
    assert got.exit_code == 0
    assert "4.0" in got.output
    assert runner.invoke(app, ["config", "validate", "--path", str(path)]).exit_code == 0
    assert "valid" in runner.invoke(app, ["config", "validate", "--path", str(path)]).output.lower()
    path_cmd = runner.invoke(app, ["config", "path"])
    assert path_cmd.exit_code == 0
    assert "Exists" in path_cmd.output


def test_config_invalid_text_errors(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("[general]\nlog_level = 'LOUD'\n")
    result = runner.invoke(app, ["config", "validate", "--path", str(bad)])
    assert result.exit_code == 1
    assert "Configuration invalid" in result.output
    unknown = runner.invoke(app, ["config", "get", "nope.key", "--path", str(bad)])
    assert unknown.exit_code == 1
    assert "Error" in unknown.output


def test_config_init_twice_requires_force(tmp_path):
    path = tmp_path / "config.toml"
    runner.invoke(app, ["config", "init", "--path", str(path)])
    second = runner.invoke(app, ["config", "init", "--path", str(path)])
    assert second.exit_code == 1
    assert "already exists" in second.output.lower()
    forced = runner.invoke(app, ["config", "init", "--path", str(path), "--force"])
    assert forced.exit_code == 0


def test_config_set_unknown_key_and_bad_type(tmp_path):
    path = tmp_path / "config.toml"
    runner.invoke(app, ["config", "init", "--path", str(path)])
    unknown = runner.invoke(app, ["config", "set", "nope.key", "1", "--path", str(path)])
    assert unknown.exit_code == 1
    assert "Unknown key" in unknown.output
    boolean = runner.invoke(app, ["config", "set", "general.colors", "maybe", "--path", str(path)])
    assert boolean.exit_code == 1
    assert "Boolean" in boolean.output


# --- json stays clean in every group --------------------------------------


def test_text_mode_never_emits_json_for_system_cpu():
    result = runner.invoke(app, ["system", "cpu"])
    assert result.exit_code == 0
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.output)
