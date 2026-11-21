"""Network tests."""

import socket
from unittest.mock import patch

from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.network_service import get_interfaces, get_ports, resolve_dns

runner = CliRunner()


def test_dns_localhost():
    result = resolve_dns("localhost")
    # localhost should resolve to 127.0.0.1
    assert result.domain == "localhost"
    if result.error is None:
        assert result.ipv4 or result.ipv6


def test_dns_invalid(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *args: (_ for _ in ()).throw(socket.gaierror("not found"))
    )
    result = resolve_dns("this-domain-definitely-does-not-exist-xyz123.invalid")
    assert result.error or not result.ipv4


def test_ports_callable():
    ports = get_ports()
    assert isinstance(ports, list)


def test_interfaces_callable():
    ifaces = get_interfaces()
    assert isinstance(ifaces, list)
    # Should have at least loopback
    assert len(ifaces) >= 1


def test_net_dns_cli_invalid(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *args: (_ for _ in ()).throw(socket.gaierror("not found"))
    )
    result = runner.invoke(
        app, ["net", "dns", "this-domain-definitely-does-not-exist-xyz123.invalid"]
    )
    assert result.exit_code == 1  # DNS failure is reported to scripts


def test_net_interfaces_json():
    result = runner.invoke(app, ["net", "interfaces", "--json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert isinstance(data, list)


def test_net_ports_json():
    result = runner.invoke(app, ["net", "ports", "--json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert isinstance(data, list)


def test_net_http_invalid():
    result = runner.invoke(app, ["net", "http", "http://localhost:1", "--json"])
    assert result.exit_code == 1
    import json

    data = json.loads(result.output)
    assert "url" in data


def test_ping_mock():
    from forgekit.services.network_service import ping_host

    with patch(
        "forgekit.services.network_service.socket.getaddrinfo",
        return_value=[(2, 1, 6, "", ("1.1.1.1", 0))],
    ):
        with (
            patch("forgekit.services.network_service.shutil.which", return_value="/usr/bin/ping"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value.stdout = "4 packets transmitted, 4 received, 0% packet loss\nrtt min/avg/max/mdev = 10.0/12.0/14.0/1.0 ms\ntime=12.0 ms\ntime=11.0 ms\n"
            mock_run.return_value.stderr = ""
            mock_run.return_value.returncode = 0
            result = ping_host("example.com", count=2, timeout=2)
            assert result.host == "example.com"
            assert result.packets_sent == 2
            assert result.packets_received == 2
            assert result.success and result.method == "icmp"
