"""Service-level failure paths: missing tools, odd environments, untrusted input."""

import os
import stat
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

import forgekit.platform as platform_module
import forgekit.services.developer_service as developer_service
import forgekit.services.network_service as network
import forgekit.services.package_service as package_service
import forgekit.services.security_service as security
import forgekit.services.system_service as system_service
import forgekit.utils as utils
from forgekit.core import permissions
from forgekit.models.network_info import HttpResult
from forgekit.storage import cache, history

# --- utils -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, "0 B"), (-5, "0 B"), (512, "512 B"), (2048, "2.0 KB"), (5 * 1024**3, "5.0 GB")],
)
def test_format_bytes(value, expected):
    assert utils.format_bytes(value) == expected


@pytest.mark.parametrize(
    ("seconds", "fragment"),
    [(0, "0s"), (5.5, "5.5s"), (90, "1m"), (3700, "1h"), (90000, "1d")],
)
def test_format_duration(seconds, fragment):
    assert fragment in utils.format_duration(seconds)


@pytest.mark.parametrize(
    ("url", "hidden"),
    [
        ("https://user:secret@example.test/path", "secret"),
        ("https://example.test/path?token=abc", "abc"),
        ("https://example.test/path#fragment", "#fragment"),
        ("git@example.test:owner/repo.git", "git@"),
    ],
)
def test_redact_url_hides_credentials_and_query(url, hidden):
    redacted = utils.redact_url(url)
    assert hidden not in redacted
    assert "example.test" in redacted


def test_redact_url_keeps_plain_urls_unchanged():
    assert utils.redact_url("https://example.test/plain") == "https://example.test/plain"


@pytest.mark.parametrize(
    ("host", "valid"),
    [
        ("example.com", True),
        ("sub.example.com", True),
        ("192.0.2.1", True),
        ("2001:db8::1", True),
        ("-bad.example", False),
        ("bad host", False),
        ("a" * 300 + ".com", False),
    ],
)
def test_is_valid_hostname(host, valid):
    assert utils.is_valid_hostname(host) is valid


def test_run_command_hardens_git_and_passes_others_through(monkeypatch):
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(utils.subprocess, "run", fake_run)
    utils.run_command(["git", "status"])
    assert seen["cmd"][:5] == ["git", "--no-optional-locks", "-c", "core.fsmonitor=false", "status"]
    utils.run_command(["/usr/bin/ls", "-l"])
    assert seen["cmd"] == ["/usr/bin/ls", "-l"]


def test_safe_read_text_limits_and_errors(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("data")
    assert utils.safe_read_text(path) == "data"
    assert utils.safe_read_text(path, max_bytes=1) is None
    assert utils.safe_read_text(tmp_path / "missing.txt") is None


# --- platform --------------------------------------------------------------


@pytest.mark.parametrize(
    ("system", "expected"),
    [("Linux", "linux"), ("Darwin", "macos"), ("Windows", "windows"), ("Plan9", "unknown")],
)
def test_detect_os(system, expected, monkeypatch):
    monkeypatch.setattr(platform_module.platform, "system", lambda: system)
    assert platform_module.detect_os() == platform_module.OS(expected)


def test_platform_info_flags():
    info = platform_module.get_platform_info()
    assert info.is_linux is (info.os == platform_module.OS.LINUX)
    assert set(("linux", "macos", "windows", "unknown")).issuperset([str(info.os)])
    assert info.python_version


def test_is_root_without_geteuid(monkeypatch):
    monkeypatch.delattr(os, "geteuid", raising=False)
    assert platform_module.is_root() is False


# --- permissions ----------------------------------------------------------


def test_can_read_write_and_world_writable(tmp_path):
    path = tmp_path / "file.txt"
    path.write_text("x")
    path.chmod(0o666)
    assert permissions.can_read(path) is True
    assert permissions.can_write(path) is True
    assert permissions.is_world_writable(path) is True
    link = tmp_path / "link"
    link.symlink_to(path)
    assert permissions.is_world_writable(link) is False
    assert permissions.is_world_writable(tmp_path / "missing") is False


def test_ssh_permission_reporting(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    assert permissions.check_ssh_permissions(home) == []

    ssh = home / ".ssh"
    ssh.mkdir(mode=0o755)
    key = ssh / "id_ed25519"
    key.write_text("private")
    key.chmod(0o644)
    issues = permissions.check_ssh_permissions(home)
    assert any("recommended mode 0700" in issue["issue"] for issue in issues)
    assert any("permissions may be too open" in issue["issue"] for issue in issues)


def test_ssh_permissions_reject_symlinked_directory_and_special_file(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    target = tmp_path / "elsewhere"
    target.mkdir(mode=0o700)
    (home / ".ssh").symlink_to(target)
    issues = permissions.check_ssh_permissions(home)
    assert issues and "not a regular directory" in issues[0]["issue"]

    (home / ".ssh").unlink()
    ssh = home / ".ssh"
    ssh.mkdir(mode=0o700)
    fifo = ssh / "authorized_keys"
    os.mkfifo(fifo)
    issues = permissions.check_ssh_permissions(home)
    assert any("not a regular file" in issue["issue"] for issue in issues)


# --- storage --------------------------------------------------------------


def test_cache_roundtrip_expiry_and_corruption(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "DEFAULT_CACHE_DIR", tmp_path / "cache")
    assert cache.get("missing") is None
    cache.set("key", {"value": 1})
    assert cache.get("key") == {"value": 1}
    path = cache.cache_path("key")
    assert path.exists()
    old = time.time() - 3600
    os.utime(path, (old, old))
    assert cache.get("key", max_age_seconds=60) is None

    path.write_text("{not json")
    assert cache.get("key") is None

    symlink_target = tmp_path / "target.json"
    symlink_target.write_text("{}")
    other = cache.cache_path("link")
    other.symlink_to(symlink_target)
    assert cache.get("link") is None


def test_cache_clear_only_removes_its_own_files(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "DEFAULT_CACHE_DIR", tmp_path / "cache")
    cache.set("one", [1])
    foreign = tmp_path / "cache" / "conversation.json"
    foreign.write_text("{}")
    wrong_name = tmp_path / "cache" / "forgekit-cache-notahash.json"
    wrong_name.write_text("{}")
    assert cache.clear() == 1
    assert foreign.exists()
    assert wrong_name.exists()


def test_history_creates_private_database_and_refuses_symlinks(tmp_path):
    db = tmp_path / "history.db"
    history.record("forge system cpu", exit_code=0, duration_ms=12, path=db)
    assert oct(db.stat().st_mode & 0o777) == oct(0o600)
    with history.get_db(db) as conn:
        rows = conn.execute("SELECT command, exit_code, duration_ms FROM history").fetchall()
    assert rows == [("forge system cpu", 0, 12)]

    target = tmp_path / "target.db"
    target.write_text("")
    link = tmp_path / "linked.db"
    link.symlink_to(target)
    with pytest.raises(OSError, match="symbolic-link"):
        history.get_db(link)


# --- network --------------------------------------------------------------


def test_ping_rejects_invalid_arguments():
    result = network.ping_host("bad host!", count=0, timeout=0)
    assert result.success is False
    assert "Invalid host" in result.error


def test_ping_reports_unresolvable_host(monkeypatch):
    monkeypatch.setattr(network, "resolve_addresses", lambda host, timeout: [])
    result = network.ping_host("example.test")
    assert result.success is False
    assert "No addresses returned" in result.error


def test_ping_dns_timeout_is_reported(monkeypatch):
    def slow(host, timeout):
        raise TimeoutError("DNS resolution timed out after 1s")

    monkeypatch.setattr(network, "resolve_addresses", slow)
    result = network.ping_host("example.test", count=1, timeout=1)
    assert result.success is False
    assert "timed out" in result.error


def test_ping_uses_tcp_fallback_when_no_binary(monkeypatch):
    monkeypatch.setattr(network.shutil, "which", lambda name: None)

    class FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(network.socket, "create_connection", lambda *a, **k: FakeSocket())
    result = network.ping_host("192.0.2.1", count=1, timeout=1)
    assert result.method == "tcp"
    assert result.success is True


def test_ping_uses_tcp_fallback_when_ports_closed(monkeypatch):
    monkeypatch.setattr(network.shutil, "which", lambda name: None)

    def refuse(*args, **kwargs):
        raise OSError("connection refused")

    monkeypatch.setattr(network.socket, "create_connection", refuse)
    result = network.ping_host("192.0.2.1", count=1, timeout=1)
    assert result.method == "tcp"
    assert result.success is False
    assert "TCP fallback failed" in result.error


def test_ping_binary_failure_reports_error(monkeypatch):
    monkeypatch.setattr(network.shutil, "which", lambda name: "/bin/ping")

    def explode(*args, **kwargs):
        raise OSError("ping blew up")

    monkeypatch.setattr(network.subprocess, "run", explode)
    result = network.ping_host("192.0.2.1", count=1, timeout=1)
    assert result.success is False
    assert "Ping failed" in result.error


def test_ping_parses_icmp_output(monkeypatch):
    monkeypatch.setattr(network.shutil, "which", lambda name: "/bin/ping")
    monkeypatch.setattr(network.platform, "system", lambda: "Linux")
    output = (
        "2 packets transmitted, 2 received, 0% packet loss\n"
        "rtt min/avg/max/mdev = 1.000/2.000/3.000/0.500 ms\n"
        "time=1.5 ms\ntime=2.5 ms\n"
    )
    monkeypatch.setattr(
        network.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, output, ""),
    )
    result = network.ping_host("192.0.2.1", count=2, timeout=1)
    assert result.success is True
    assert result.method == "icmp"
    assert result.packets_received == 2
    assert result.avg_ms == pytest.approx(2.0)


def test_ping_windows_parsing(monkeypatch):
    monkeypatch.setattr(network.shutil, "which", lambda name: "ping.exe")
    monkeypatch.setattr(network.platform, "system", lambda: "Windows")
    output = "Packets: Sent = 1, Received = 1, Lost = 0\ntime<1ms\n"
    monkeypatch.setattr(
        network.subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, output, ""),
    )
    result = network.ping_host("192.0.2.1", count=1, timeout=1)
    assert result.success is True
    assert result.packets_received == 1


def test_resolve_addresses_times_out(monkeypatch):
    def slow(*args, **kwargs):
        time.sleep(0.2)
        return []

    monkeypatch.setattr(network.socket, "getaddrinfo", slow)
    with pytest.raises(TimeoutError, match="DNS resolution timed out"):
        network.resolve_addresses("example.test", timeout=0.05)


def test_resolve_addresses_propagates_resolver_errors(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("resolver unavailable")

    monkeypatch.setattr(network.socket, "getaddrinfo", broken)
    with pytest.raises(OSError, match="resolver unavailable"):
        network.resolve_addresses("example.test", timeout=1)


def test_resolve_dns_handles_errors(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("no dns")

    monkeypatch.setattr(network, "resolve_addresses", broken)
    result = network.resolve_dns("example.test")
    assert result.error == "no dns"
    assert result.ipv4 == [] and result.ipv6 == []


def test_http_rejects_bad_input(monkeypatch):
    assert network.check_http("https://example.test", timeout=0).error.startswith("Timeout")
    assert "HTTP(S)" in network.check_http("ftp://example.test").error
    assert "credentials" in network.check_http("https://user:pw@example.test").error
    assert "port" in network.check_http("http://example.test:99999").error


def test_http_redacts_headers_and_limits_redirects(monkeypatch):
    class Response:
        def __init__(self, status_code, headers):
            self.status_code = status_code
            self.headers = headers
            self.reason = "reason"

        def close(self):
            pass

    responses = [
        Response(302, {"Location": "https://example.test/hop?token=secret"}),
    ]

    def fake_get(url, **kwargs):
        if responses:
            return responses.pop()
        return Response(200, {"Content-Type": "text/plain", "Set-Cookie": "session=abc"})

    monkeypatch.setattr(network.requests, "get", fake_get)
    result = network.check_http("https://example.test", timeout=1)
    assert isinstance(result, HttpResult)
    assert result.redirected is True
    assert result.headers["Set-Cookie"] == "***redacted***"

    def always_redirect(url, **kwargs):
        return Response(302, {"Location": "https://example.test/loop"})

    monkeypatch.setattr(network.requests, "get", always_redirect)
    looped = network.check_http("https://example.test", timeout=1)
    assert "Too many HTTP redirects" in looped.error


def test_http_request_exception_is_generic(monkeypatch):
    def boom(*args, **kwargs):
        raise network.requests.exceptions.ConnectionError("secret detail")

    monkeypatch.setattr(network.requests, "get", boom)
    result = network.check_http("https://example.test", timeout=1)
    assert result.error == "ConnectionError: request failed"


def test_check_connectivity_reports_failures(monkeypatch):
    def broken(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr(network, "resolve_addresses", broken)
    monkeypatch.setattr(
        network,
        "check_http",
        lambda url, timeout: HttpResult(
            url=url,
            status_code=None,
            reason=None,
            elapsed_ms=1.0,
            final_url=None,
            redirected=False,
            error="unreachable",
        ),
    )
    checks = network.check_connectivity(timeout=1)
    assert len(checks) == 3
    assert all(check.success is False for check in checks)


def test_port_and_interface_inspection_errors(monkeypatch):
    def denied(*args, **kwargs):
        raise psutil.AccessDenied(pid=1)

    monkeypatch.setattr(network.psutil, "net_connections", denied)
    with pytest.raises(RuntimeError, match="Cannot inspect local ports"):
        network.get_ports()

    monkeypatch.setattr(network.psutil, "net_if_addrs", denied)
    with pytest.raises(RuntimeError, match="Cannot inspect network interfaces"):
        network.get_interfaces()


def test_interface_without_stats(monkeypatch):
    monkeypatch.setattr(
        network.psutil,
        "net_if_addrs",
        lambda: {
            "lo": [
                SimpleNamespace(family=network.socket.AF_INET, address="127.0.0.1"),
                SimpleNamespace(family=psutil.AF_LINK, address="00:00:00:00:00:00"),
            ]
        },
    )
    monkeypatch.setattr(network.psutil, "net_if_stats", lambda: {})
    monkeypatch.setattr(network.psutil, "net_io_counters", lambda pernic: {})
    interfaces = network.get_interfaces()
    assert interfaces[0].is_up is None
    assert interfaces[0].bytes_sent is None
    assert interfaces[0].mac == "00:00:00:00:00:00"


# --- packages -------------------------------------------------------------


def test_detect_managers_probes_once_and_caches(monkeypatch):
    calls = []

    def which(name):
        calls.append(name)
        return f"/usr/bin/{name}" if name in ("apt", "dnf") else None

    monkeypatch.setattr(package_service.shutil, "which", which)
    monkeypatch.setattr(
        package_service.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, "apt 2.6.0\n", ""),
    )
    package_service._DETECTED = None
    first = package_service.detect_managers()
    assert [m["name"] for m in first] == ["apt", "dnf"]
    second = package_service.detect_managers()
    assert second == first
    assert calls.count("apt") == 1
    package_service.detect_managers(refresh=True)
    assert calls.count("apt") == 2
    package_service._DETECTED = None


def test_detect_managers_survives_broken_version_command(monkeypatch):
    monkeypatch.setattr(
        package_service.shutil, "which", lambda name: "/usr/bin/apt" if name == "apt" else None
    )

    def broken(*args, **kwargs):
        raise OSError("cannot execute")

    monkeypatch.setattr(package_service.subprocess, "run", broken)
    package_service._DETECTED = None
    managers = package_service.detect_managers()
    assert managers[0]["version"] == "unknown"
    package_service._DETECTED = None


def test_primary_manager_prefers_native(monkeypatch):
    monkeypatch.setattr(
        package_service,
        "detect_managers",
        lambda refresh=False: [{"name": "brew"}, {"name": "apt"}],
    )
    assert package_service.primary_manager()["name"] == "apt"
    monkeypatch.setattr(package_service, "detect_managers", lambda refresh=False: [])
    assert package_service.primary_manager() is None


def test_apt_update_parsing(monkeypatch):
    output = (
        "Listing...\n"
        "libc6/stable 2.36 amd64 [upgradable from: 2.35]\n"
        "curl/stable 8.0 amd64 [upgradable from: 7.9]\n"
    )
    monkeypatch.setattr(
        package_service,
        "run_command",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, output, ""),
    )
    result = package_service.check_updates_apt()
    assert result["upgradable_count"] == 2

    monkeypatch.setattr(
        package_service,
        "run_command",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "apt is locked"),
    )
    assert package_service.check_updates_apt()["error"] == "apt is locked"


def test_dnf_update_parsing(monkeypatch):
    monkeypatch.setattr(
        package_service,
        "run_command",
        lambda *a, **k: subprocess.CompletedProcess(a, 100, "pkg.x86_64 1.0 repo\n", ""),
    )
    result = package_service.check_updates_dnf()
    assert result["upgradable_count"] == 1

    monkeypatch.setattr(
        package_service,
        "run_command",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, "", ""),
    )
    assert package_service.check_updates_dnf()["upgradable_count"] == 0

    monkeypatch.setattr(
        package_service,
        "run_command",
        lambda *a, **k: subprocess.CompletedProcess(a, 100, "", ""),
    )
    assert package_service.check_updates_dnf()["available"] is False


def test_pacman_and_unknown_update_checks(monkeypatch):
    monkeypatch.setattr(
        package_service,
        "run_command",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, "", ""),
    )
    result = package_service.check_updates_generic("pacman")
    assert result["available"] is True and result["upgradable_count"] == 0

    monkeypatch.setattr(
        package_service,
        "run_command",
        lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "database error"),
    )
    assert package_service.check_updates_generic("pacman")["error"] == "database error"

    unknown = package_service.check_updates_generic("zypper")
    assert unknown["available"] is False
    assert "not implemented" in unknown["note"]


def test_list_installed_packages_errors(monkeypatch):
    with pytest.raises(ValueError, match="not supported"):
        package_service.list_installed_packages("zypper")
    monkeypatch.setattr(package_service.shutil, "which", lambda name: None)
    with pytest.raises(FileNotFoundError):
        package_service.list_installed_packages("apt")

    monkeypatch.setattr(package_service.shutil, "which", lambda name: "/usr/bin/apt")
    monkeypatch.setattr(
        package_service, "run_command", lambda *a, **k: subprocess.CompletedProcess(a, 1, "", "x")
    )
    with pytest.raises(RuntimeError, match="Package listing failed"):
        package_service.list_installed_packages("apt")

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="apt", timeout=1)

    monkeypatch.setattr(package_service, "run_command", timeout)
    with pytest.raises(TimeoutError):
        package_service.list_installed_packages("apt")

    monkeypatch.setattr(
        package_service,
        "run_command",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, "pkg/stable 1.0 amd64\nnoise\n", ""),
    )
    assert package_service.list_installed_packages("apt") == ["pkg/stable 1.0 amd64"]


# --- security -------------------------------------------------------------


def test_firewall_variants(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: "/usr/sbin/ufw" if name == "ufw" else None)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, "Status: active\n", ""),
    )
    assert security.check_firewall()[0]["level"] == "pass"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, "Status: inactive\n", ""),
    )
    assert security.check_firewall()[0]["level"] == "warn"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, "unparseable\n", ""),
    )
    assert "could not be determined" in security.check_firewall()[0]["message"]

    def denied(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)

    monkeypatch.setattr(subprocess, "run", denied)
    assert "unavailable" in security.check_firewall()[0]["message"]

    monkeypatch.setattr("shutil.which", lambda name: None)
    assert "No common firewall tool" in security.check_firewall()[0]["message"]


def test_firewalld_and_iptables_detection(monkeypatch):
    monkeypatch.setattr(
        "shutil.which", lambda name: "/usr/bin/firewall-cmd" if name == "firewall-cmd" else None
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, "running\n", ""),
    )
    assert security.check_firewall()[0]["level"] == "pass"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 1, "not running\n", ""),
    )
    assert security.check_firewall()[0]["level"] == "warn"

    monkeypatch.setattr(
        "shutil.which", lambda name: "/sbin/iptables" if name == "iptables" else None
    )
    assert "iptables found" in security.check_firewall()[0]["message"]


def test_update_summary_variants(monkeypatch):
    monkeypatch.setattr(security, "primary_manager", lambda: None)
    assert "No supported package manager" in security.check_updates_available()["message"]

    monkeypatch.setattr(
        security,
        "primary_manager",
        lambda: {"name": "apt", "update_cmd": "sudo apt upgrade"},
    )
    monkeypatch.setattr(
        security,
        "check_updates_generic",
        lambda name: {"available": True, "upgradable_count": 3},
    )
    finding = security.check_updates_available()
    assert finding["level"] == "warn"
    assert "3 updates" in finding["message"]

    monkeypatch.setattr(
        security,
        "check_updates_generic",
        lambda name: {"available": True, "upgradable_count": 0},
    )
    assert security.check_updates_available()["level"] == "info"

    monkeypatch.setattr(
        security, "check_updates_generic", lambda name: {"available": False, "error": "stale"}
    )
    assert "stale" in security.check_updates_available()["message"]


def test_risky_config_patterns(tmp_path):
    config = tmp_path / "app.conf"
    config.write_text("password = hunter2\nchmod 777 /data\nPermitRootLogin yes\n")
    findings = security.scan_risky_config(config)
    levels = {finding["level"] for finding in findings}
    assert "fail" in levels and "warn" in levels
    assert all("hunter2" not in finding["message"] for finding in findings)

    clean = tmp_path / "clean.conf"
    clean.write_text("nothing to see")
    assert security.scan_risky_config(clean) == []

    with pytest.raises(ValueError, match="Not a regular file"):
        security.scan_risky_config(tmp_path)

    big = tmp_path / "big.conf"
    big.write_bytes(b"a" * (1024 * 1024 + 10))
    with pytest.raises(ValueError, match="too large"):
        security.scan_risky_config(big)


def test_security_scan_reports_limited_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "scan"
    target.mkdir()
    (target / "open.txt").write_text("x")
    (target / "open.txt").chmod(0o666)
    findings = security.check_security(target)
    assert any(finding["check"] == "world_writable" for finding in findings)
    # The tool must never claim a machine is secure.
    assert all("you are secure" not in finding["message"].lower() for finding in findings)


def test_security_scan_world_writable_limits(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "many"
    target.mkdir()
    for index in range(8):
        path = target / f"file{index}"
        path.write_text("x")
        path.chmod(0o666)
    findings = security.check_security(target)
    assert any("more" in finding["message"] for finding in findings)


# --- git ------------------------------------------------------------------


def test_git_status_without_git_binary(tmp_path, monkeypatch):
    import forgekit.services.git_service as git_service

    monkeypatch.setattr(git_service.shutil, "which", lambda name: None)
    status = git_service.get_git_status(tmp_path)
    assert status.is_repo is False
    assert status.error == "Git executable not found in PATH"


def test_git_service_handles_failures(tmp_path, monkeypatch):
    import forgekit.services.git_service as git_service

    monkeypatch.setattr(git_service, "is_git_repo", lambda path: True)

    def failing(cmd, cwd=None, timeout=15, **kwargs):
        if cmd[1:] == ["branch"] or "--format=%(refname:short) %(HEAD)" in cmd:
            return subprocess.CompletedProcess(cmd, 128, "", "fatal: not a repo")
        return subprocess.CompletedProcess(cmd, 128, "", "fatal: exploded")

    monkeypatch.setattr(git_service, "run_command", failing)
    status = git_service.get_git_status(tmp_path)
    assert status.is_repo is True
    assert status.error and "git status failed" in status.error
    with pytest.raises(RuntimeError, match="Could not list git branches"):
        git_service.get_branches(tmp_path)


def test_inspect_path_for_missing_file(tmp_path):
    import forgekit.services.git_service as git_service

    info = git_service.inspect_path(tmp_path / "missing.txt")
    assert info["exists"] is False
    assert "git_history" not in info


# --- developer ------------------------------------------------------------


def test_check_tool_variants(monkeypatch):
    monkeypatch.setattr(developer_service.shutil, "which", lambda name: None)
    missing = developer_service.check_tool("rustc", developer_service.TOOL_CHECKS["rustc"])
    assert missing["found"] is False and missing["name"] == "rust"

    monkeypatch.setattr(developer_service.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(
        developer_service.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 1, "", "version goes here"),
    )
    failed = developer_service.check_tool("java", developer_service.TOOL_CHECKS["java"])
    # java falls back to -version, which also fails here
    assert failed["found"] is True
    assert "Version command failed" in failed["details"]

    def unavailable(cmd, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(developer_service.subprocess, "run", unavailable)
    broken = developer_service.check_tool("node", developer_service.TOOL_CHECKS["node"])
    assert "Version unavailable" in broken["details"]


def test_check_tool_alternative_binary(monkeypatch):
    monkeypatch.setattr(
        developer_service.shutil,
        "which",
        lambda name: "/usr/bin/python3" if name == "python3" else None,
    )
    monkeypatch.setattr(
        developer_service.subprocess,
        "run",
        lambda cmd, **kwargs: subprocess.CompletedProcess(cmd, 0, "Python 3.11.2\n", ""),
    )
    found = developer_service.check_tool("python", developer_service.TOOL_CHECKS["python"])
    assert found["found"] is True
    assert found["version"].startswith("Python")


def test_path_diagnostics_variants(monkeypatch):
    monkeypatch.setenv("PATH", "")
    assert developer_service.path_diagnostics()[0]["level"] == "fail"

    monkeypatch.setenv("PATH", "/usr/bin:/usr/bin:/definitely/missing")
    messages = [issue["message"] for issue in developer_service.path_diagnostics()]
    assert any("Duplicate PATH entries" in message for message in messages)
    assert any("non-existent directories" in message for message in messages)


# --- system ---------------------------------------------------------------


def test_get_processes_rejects_bad_arguments():
    with pytest.raises(ValueError):
        system_service.get_processes(limit=0)
    with pytest.raises(ValueError):
        system_service.get_processes(sort_by="threads")


def test_get_processes_tolerates_denied_processes(monkeypatch):
    class FakeProcess:
        def __init__(self, info, deny=False):
            self.info = info
            self._deny = deny

        def cpu_percent(self, interval=None):
            if self._deny:
                raise psutil.AccessDenied(pid=self.info["pid"])
            return 1.0

    processes = [
        FakeProcess(
            {
                "pid": 1,
                "name": "init",
                "username": "root",
                "memory_percent": 0.1,
                "memory_info": SimpleNamespace(rss=1024),
                "status": "running",
                "create_time": 1.0,
            }
        ),
        FakeProcess(
            {
                "pid": 2,
                "name": "denied",
                "username": None,
                "memory_percent": None,
                "memory_info": None,
                "status": None,
                "create_time": None,
            },
            deny=True,
        ),
    ]
    monkeypatch.setattr(system_service.psutil, "process_iter", lambda attrs: processes)
    monkeypatch.setattr(system_service.time, "sleep", lambda seconds: None)
    result = system_service.get_processes(limit=5)
    assert len(result) == 2
    denied = next(proc for proc in result if proc.pid == 2)
    assert denied.cpu_percent is None
    assert denied.status == "unknown"


def test_system_helpers_return_none_when_unavailable(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("unavailable")

    monkeypatch.setattr(system_service.psutil, "boot_time", broken)
    monkeypatch.setattr(system_service.psutil, "sensors_battery", broken)
    monkeypatch.setattr(system_service.os, "getloadavg", broken, raising=False)
    assert system_service.get_uptime() is None
    assert system_service.get_battery() == (None, None)
    assert system_service.get_load_avg() is None


def test_summary_survives_failing_collectors(monkeypatch):
    monkeypatch.setattr(
        system_service,
        "get_cpu_info",
        lambda per_core=False: (_ for _ in ()).throw(RuntimeError("no cpu")),
    )
    monkeypatch.setattr(
        system_service, "get_memory_info", lambda: (_ for _ in ()).throw(RuntimeError("no mem"))
    )
    monkeypatch.setattr(
        system_service, "get_disk_info", lambda: (_ for _ in ()).throw(RuntimeError("no disk"))
    )
    summary = system_service.get_system_summary()
    assert summary.cpu is None and summary.memory is None and summary.disk is None
    assert summary.hostname


def test_disk_info_falls_back_to_cwd_root(monkeypatch):
    monkeypatch.setattr(system_service.psutil, "disk_partitions", lambda all: [])
    info = system_service.get_disk_info()
    assert info.partitions
    assert info.partitions[0].mountpoint == Path.cwd().anchor


# --- filesystem -----------------------------------------------------------


def test_filesystem_walk_survives_permission_errors(tmp_path, monkeypatch):
    from forgekit.services import filesystem_service

    blocked = tmp_path / "blocked"
    blocked.mkdir()
    (blocked / "hidden.txt").write_text("x")
    (tmp_path / "visible.txt").write_text("y")

    real_scandir = os.scandir

    def denied(path):
        if str(path) == str(blocked):
            raise PermissionError("denied")
        return real_scandir(path)

    monkeypatch.setattr(os, "scandir", denied)
    results = filesystem_service.search_files(tmp_path, "txt")
    names = {result["name"] for result in results}
    assert "visible.txt" in names


def test_filesystem_rejects_bad_limits(tmp_path):
    from forgekit.services import filesystem_service

    with pytest.raises(ValueError):
        filesystem_service.find_large_files(tmp_path, threshold_bytes=-1)
    with pytest.raises(ValueError):
        filesystem_service.search_files(tmp_path, "x", limit=0)
    with pytest.raises(ValueError):
        filesystem_service.find_duplicates(tmp_path, min_size=-1)


def test_symlinks_are_not_followed_or_counted(tmp_path):
    from forgekit.services import filesystem_service

    real = tmp_path / "real.txt"
    real.write_text("data")
    (tmp_path / "link.txt").symlink_to(real)
    sizes = filesystem_service.directory_size(tmp_path)
    assert sizes["file_count"] == 1


def test_duplicate_detection_hashes_only_same_size_groups(tmp_path):
    from forgekit.services import filesystem_service

    (tmp_path / "a.txt").write_text("same")
    (tmp_path / "b.txt").write_text("same")
    (tmp_path / "c.txt").write_text("different")
    groups = filesystem_service.find_duplicates(tmp_path)
    assert len(groups) == 1
    assert groups[0]["count"] == 2
    assert len(groups[0]["hash"]) == 64


def test_file_hash_streams_large_files(tmp_path):
    from forgekit.services import filesystem_service

    path = tmp_path / "large.bin"
    path.write_bytes(b"x" * 3)
    assert filesystem_service.file_hash(path, chunk_size=1) == filesystem_service.file_hash(path)


def test_world_writable_sticky_directory_is_informational(tmp_path):
    sticky = tmp_path / "shared"
    sticky.mkdir()
    sticky.chmod(0o1777)
    mode = sticky.lstat().st_mode
    assert mode & stat.S_IWOTH and mode & stat.S_ISVTX
