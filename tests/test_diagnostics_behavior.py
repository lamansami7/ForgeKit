"""Deterministic system, package, developer and security diagnostics tests."""

import json
import subprocess
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace

import psutil
from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.core.permissions import check_ssh_permissions
from forgekit.services import developer_service, package_service, security_service, system_service


def test_cpu_uses_blocking_samples_and_only_requests_per_core_when_needed(monkeypatch):
    calls = []
    monkeypatch.setattr(
        psutil,
        "cpu_percent",
        lambda interval, percpu=False: (
            calls.append((interval, percpu)) or ([10.0, 30.0] if percpu else 20.0)
        ),
    )
    monkeypatch.setattr(psutil, "cpu_freq", lambda: None)
    normal = system_service.get_cpu_info()
    assert normal.usage_percent == 20.0 and normal.per_core_percent == []
    assert calls == [(0.25, False)]
    per_core = system_service.get_cpu_info(per_core=True)
    assert per_core.per_core_percent == [10.0, 30.0]
    assert all(interval > 0 for interval, _ in calls)


def test_memory_used_matches_available_and_percent(monkeypatch):
    monkeypatch.setattr(
        psutil,
        "virtual_memory",
        lambda: SimpleNamespace(total=1000, available=400, used=500, free=100, percent=60),
    )
    monkeypatch.setattr(
        psutil, "swap_memory", lambda: SimpleNamespace(total=100, used=20, free=80, percent=20)
    )
    info = system_service.get_memory_info()
    assert info.used == 600 and info.raw_used == 500 and info.percent == 60
    assert info.swap_used == 20


def test_disk_uses_accessible_mount_and_root_fallback(monkeypatch):
    part = namedtuple("part", "device mountpoint fstype")
    usage = SimpleNamespace(total=100, used=60, free=40, percent=60)
    monkeypatch.setattr(
        psutil, "disk_partitions", lambda all: [part("d", "/denied", "x"), part("e", "/good", "y")]
    )

    def disk_usage(path):
        if path == "/denied":
            raise PermissionError("denied")
        return usage

    monkeypatch.setattr(psutil, "disk_usage", disk_usage)
    disks = system_service.get_disk_info()
    assert ("/good", 60) in [(p.mountpoint, p.percent) for p in disks.partitions]
    assert all(p.mountpoint != "/denied" for p in disks.partitions)
    assert any(p.mountpoint == "/" and p.fstype == "unknown" for p in disks.partitions)
    monkeypatch.setattr(psutil, "disk_partitions", lambda all: [])
    assert system_service.get_disk_info().partitions[0].fstype == "unknown"


def test_process_cpu_is_primed_and_sorted_after_second_sample(monkeypatch):
    class Process:
        def __init__(self, pid, cpu, memory):
            self.info = {
                "pid": pid,
                "name": f"p{pid}",
                "username": None,
                "memory_percent": memory,
                "memory_info": SimpleNamespace(rss=pid * 10),
                "status": "running",
                "create_time": 1,
            }
            self.cpu = cpu
            self.calls = 0

        def cpu_percent(self, interval=None):
            self.calls += 1
            return 0 if self.calls == 1 else self.cpu

    first, second = Process(1, 20.0, 5.0), Process(2, 5.0, 30.0)
    monkeypatch.setattr(psutil, "process_iter", lambda attrs: [first, second])
    monkeypatch.setattr(system_service.time, "sleep", lambda _: None)
    assert [p.pid for p in system_service.get_processes(limit=1, sort_by="cpu")] == [1]
    assert first.calls == second.calls == 2
    first.calls = second.calls = 0
    assert [p.pid for p in system_service.get_processes(limit=1, sort_by="memory")] == [2]


def test_package_updates_use_cache_and_parse_manager_output(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if args[0] == "apt":
            return SimpleNamespace(
                returncode=0,
                stdout="Listing...\na/stable 1 [upgradable from: 0]\nb/stable 2 [upgradable from: 1]\n",
                stderr="",
            )
        return SimpleNamespace(
            returncode=100,
            stdout="Last metadata expiration check\nfoo.x86_64 1.2 repo\nbar.noarch 3.4 repo\n",
            stderr="",
        )

    monkeypatch.setattr(package_service, "run_command", run)
    assert package_service.check_updates_apt()["upgradable_count"] == 2
    assert package_service.check_updates_dnf()["upgradable_count"] == 2
    assert "--cacheonly" in calls[1]
    monkeypatch.setattr(
        package_service,
        "run_command",
        lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired("apt", 10)),
    )
    failed = package_service.check_updates_apt()
    assert failed["available"] is False and "error" in failed


def test_package_cli_json_has_no_progress_text(monkeypatch):
    monkeypatch.setattr("forgekit.commands.packages.primary_manager", lambda: {"name": "apt"})
    monkeypatch.setattr(
        "forgekit.commands.packages.list_installed_packages", lambda manager, limit: ["pkg/arch 1"]
    )
    result = CliRunner().invoke(app, ["packages", "list", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)["packages"] == ["pkg/arch 1"]
    monkeypatch.setattr(
        "forgekit.commands.packages.check_updates_generic",
        lambda manager: {"available": False, "error": "timeout"},
    )
    result = CliRunner().invoke(app, ["packages", "updates", "--json"])
    assert result.exit_code == 1 and json.loads(result.output)["error"] == "timeout"


def test_developer_versions_missing_failure_and_java_fallback(monkeypatch):
    monkeypatch.setattr(
        developer_service.shutil, "which", lambda cmd: "/bin/java" if cmd == "java" else None
    )
    assert not developer_service.check_tool("node", {"cmd": "node"})["found"]
    results = iter(
        [
            SimpleNamespace(returncode=1, stdout="", stderr="bad option"),
            SimpleNamespace(returncode=0, stdout="", stderr='java version "1.8"\n'),
        ]
    )
    monkeypatch.setattr(developer_service.subprocess, "run", lambda *a, **k: next(results))
    java = developer_service.check_tool("java", developer_service.TOOL_CHECKS["java"])
    assert java["found"] and java["version"] == 'java version "1.8"' and java["details"] == "OK"


def test_security_scope_permissions_and_no_secret_disclosure(tmp_path, monkeypatch):
    monkeypatch.setattr(security_service, "check_firewall", lambda: [])
    monkeypatch.setattr(
        security_service,
        "check_updates_available",
        lambda: {"level": "info", "check": "updates", "message": "unknown", "fix": ""},
    )
    monkeypatch.setattr(security_service, "check_ssh_permissions", lambda: [])
    writable = tmp_path / "open.conf"
    writable.write_text("password = privatevalue\n")
    writable.chmod(0o666)
    findings = security_service.check_security(writable)
    assert any(f["check"] == "world_writable" and "open.conf" in f["message"] for f in findings)
    assert any("password" in f["message"].lower() for f in findings)
    assert "privatevalue" not in json.dumps(findings)
    assert all(f["level"] != "fail" for f in findings)


def test_ssh_permissions_distinguish_private_key_and_authorized_keys(tmp_path):
    ssh = tmp_path / ".ssh"
    ssh.mkdir(mode=0o700)
    (ssh / "id_rsa").write_text("not a real key")
    (ssh / "id_rsa").chmod(0o644)
    (ssh / "authorized_keys").write_text("placeholder")
    (ssh / "authorized_keys").chmod(0o644)
    issues = check_ssh_permissions(tmp_path)
    assert any(Path(issue["path"]).name == "id_rsa" for issue in issues)
    assert not any(Path(issue["path"]).name == "authorized_keys" for issue in issues)


def test_firewalld_not_running_is_never_marked_active(monkeypatch):
    import shutil

    monkeypatch.setattr(
        shutil, "which", lambda name: "/bin/firewall-cmd" if name == "firewall-cmd" else None
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="not running\n", stderr=""),
    )
    assert not any(finding["level"] == "pass" for finding in security_service.check_firewall())


def test_dashboard_noninteractive_prints_once_and_exits():
    result = CliRunner().invoke(app, ["dashboard", "--refresh", "1"])
    assert result.exit_code == 0
    assert "Dashboard" in result.output


def test_inaccessible_process_cpu_is_reported_as_unavailable(monkeypatch):
    class Process:
        info = {
            "pid": 3,
            "name": "restricted",
            "username": None,
            "memory_percent": 12.0,
            "memory_info": SimpleNamespace(rss=123),
            "status": "running",
            "create_time": None,
        }

        def cpu_percent(self, interval=None):
            raise psutil.AccessDenied(pid=3)

    monkeypatch.setattr(psutil, "process_iter", lambda attrs: [Process()])
    monkeypatch.setattr(system_service.time, "sleep", lambda _: None)
    result = system_service.get_processes(sort_by="memory")
    assert len(result) == 1 and result[0].pid == 3
    assert result[0].cpu_percent is None and result[0].memory_percent == 12.0


def test_update_checks_do_not_turn_unparseable_or_failed_results_into_zero(monkeypatch):
    monkeypatch.setattr(
        package_service,
        "run_command",
        lambda *a, **k: SimpleNamespace(returncode=100, stdout="unexpected output", stderr=""),
    )
    result = package_service.check_updates_dnf()
    assert result["available"] is False and "error" in result
    monkeypatch.setattr(
        package_service,
        "run_command",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout="", stderr="database is locked"),
    )
    result = package_service.check_updates_generic("pacman")
    assert result["available"] is False and "locked" in result["error"]


def test_security_reports_world_writable_directory_and_sticky_bit(tmp_path, monkeypatch):
    monkeypatch.setattr(security_service, "check_firewall", lambda: [])
    monkeypatch.setattr(
        security_service,
        "check_updates_available",
        lambda: {"level": "info", "check": "updates", "message": "unknown", "fix": ""},
    )
    monkeypatch.setattr(security_service, "check_ssh_permissions", lambda: [])
    directory = tmp_path / "shared"
    directory.mkdir()
    directory.chmod(0o1777)
    findings = security_service.check_security(directory)
    match = [
        item
        for item in findings
        if item["check"] == "world_writable" and str(directory) in item["message"]
    ]
    assert match and match[0]["level"] == "info" and "sticky" in match[0]["message"]


def test_security_update_check_counts_only_parsed_cached_packages(monkeypatch):
    monkeypatch.setattr(
        security_service,
        "primary_manager",
        lambda: {"name": "apt", "update_cmd": "sudo apt upgrade"},
    )
    monkeypatch.setattr(
        security_service,
        "check_updates_generic",
        lambda name: {"available": True, "upgradable_count": 0},
    )
    finding = security_service.check_updates_available()
    assert finding["level"] == "info" and finding["message"].startswith("0 updates")
    assert "cached" in finding["message"]
    monkeypatch.setattr(
        security_service,
        "check_updates_generic",
        lambda name: {"available": False, "error": "cache unavailable"},
    )
    assert "unavailable" in security_service.check_updates_available()["message"]


def test_security_config_scan_reports_oversized_file(tmp_path):
    path = tmp_path / "large.conf"
    path.write_bytes(b"x" * (1024 * 1024 + 1))
    result = CliRunner().invoke(app, ["security", "scan", str(path), "--json"])
    assert result.exit_code == 1
    assert "too large" in json.loads(result.output)["error"]


def test_firewall_timeout_is_reported_as_unavailable_not_absent(monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: "/bin/ufw" if name == "ufw" else None)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("ufw", 5)

    monkeypatch.setattr(subprocess, "run", timeout)
    finding = security_service.check_firewall()[0]
    assert finding["level"] == "info"
    assert "unavailable" in finding["message"] and "TimeoutExpired" in finding["message"]
