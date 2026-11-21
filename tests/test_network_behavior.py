"""Deterministic network behavior tests; no external network is required."""

import json
import socket
from types import SimpleNamespace

import psutil
import pytest
import requests
from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.network_service import check_http, get_ports, ping_host, resolve_dns


def test_dns_returns_ipv4_ipv6_and_handles_failure(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args: [
            (socket.AF_INET, 1, 6, "", ("192.0.2.1", 0)),
            (socket.AF_INET6, 1, 6, "", ("2001:db8::1", 0, 0, 0)),
            (socket.AF_INET, 1, 6, "", ("192.0.2.1", 0)),
        ],
    )
    result = resolve_dns("example.test")
    assert result.ipv4 == ["192.0.2.1"]
    assert result.ipv6 == ["2001:db8::1"]
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *args: (_ for _ in ()).throw(socket.gaierror("not found"))
    )
    assert resolve_dns("example.test").error == "not found"


class Response:
    def __init__(self, status, headers=None, reason="OK"):
        self.status_code = status
        self.headers = headers or {}
        self.reason = reason
        self.closed = False

    def close(self):
        self.closed = True


def test_http_streams_without_reading_bodies_and_redacts_secrets(monkeypatch):
    response = Response(
        200,
        {
            "Set-Cookie": "session=private",
            "X-Api-Key": "secret",
            "Content-Type": "text/plain",
            "Location": "/next?token=hidden",
        },
    )
    calls = []

    def request(url, **kwargs):
        calls.append((url, kwargs))
        return response

    monkeypatch.setattr(requests, "get", request)
    result = check_http("https://example.test/resource?token=private")
    assert result.status_code == 200
    assert result.url == "https://example.test/resource?***"
    assert result.headers["Set-Cookie"] == "***redacted***"
    assert result.headers["X-Api-Key"] == "***redacted***"
    assert result.headers["Location"] == "/next?***"
    assert result.headers["Content-Type"] == "text/plain"
    assert calls[0][1]["stream"] is True
    assert calls[0][1]["allow_redirects"] is False
    assert calls[0][1]["timeout"] == 10
    assert response.closed
    assert "private" not in json.dumps(result.to_dict())
    assert "secret" not in json.dumps(result.to_dict())


def test_http_redirects_are_bounded_and_closed(monkeypatch):
    responses = [Response(302, {"Location": "/new?secret=x"}), Response(200)]
    calls = []

    def get(url, **kwargs):
        calls.append(url)
        return responses[len(calls) - 1]

    monkeypatch.setattr(requests, "get", get)
    result = check_http("https://example.test/start")
    assert result.redirected and result.final_url == "https://example.test/new?***"
    assert calls == ["https://example.test/start", "https://example.test/new?secret=x"]
    assert all(response.closed for response in responses)


def test_http_rejects_url_credentials_and_redacts_exception(monkeypatch):
    result = check_http("https://user:password@example.test/?token=hidden")
    assert result.error and "password" not in json.dumps(result.to_dict())

    def fail(*args, **kwargs):
        raise requests.exceptions.SSLError("url contained token=supersecret")

    monkeypatch.setattr(requests, "get", fail)
    result = check_http("https://example.test/?token=supersecret")
    assert "SSLError" in result.error
    assert "supersecret" not in json.dumps(result.to_dict())


def test_redirect_to_non_http_or_userinfo_is_not_fetched(monkeypatch):
    response = Response(302, {"Location": "https://user:secret@other.test/private"})
    calls = []
    monkeypatch.setattr(requests, "get", lambda url, **kwargs: calls.append(url) or response)
    result = check_http("https://example.test")
    assert result.error and calls == ["https://example.test"]
    assert "secret" not in json.dumps(result.to_dict())


def test_ports_include_udp_bound_sockets_and_handle_permissions(monkeypatch):
    conns = [
        SimpleNamespace(
            type=socket.SOCK_STREAM, status=psutil.CONN_LISTEN, laddr=("::1", 80), pid=None
        ),
        SimpleNamespace(
            type=socket.SOCK_STREAM, status=psutil.CONN_ESTABLISHED, laddr=("::1", 81), pid=None
        ),
        SimpleNamespace(
            type=socket.SOCK_DGRAM, status=psutil.CONN_NONE, laddr=("127.0.0.1", 53), pid=None
        ),
    ]
    monkeypatch.setattr(psutil, "net_connections", lambda kind: conns)
    ports = get_ports()
    assert [(p.proto, p.local_port) for p in ports] == [("udp", 53), ("tcp", 80)]
    monkeypatch.setattr(
        psutil, "net_connections", lambda kind: (_ for _ in ()).throw(psutil.AccessDenied())
    )
    with pytest.raises(RuntimeError, match="Cannot inspect"):
        get_ports()
    result = CliRunner().invoke(app, ["net", "ports", "--json"])
    assert result.exit_code == 1
    assert "error" in json.loads(result.output)


def test_ping_rejects_option_injection_and_supports_ipv6(monkeypatch):
    called = []
    monkeypatch.setattr("forgekit.services.network_service.shutil.which", lambda _: "/usr/bin/ping")
    monkeypatch.setattr(
        "forgekit.services.network_service.subprocess.run",
        lambda cmd, **kw: (
            called.append(cmd)
            or SimpleNamespace(
                stdout="1 packets transmitted, 1 received, 0% packet loss\ntime=1.2 ms",
                stderr="",
                returncode=0,
            )
        ),
    )
    assert not ping_host("-c", 1).success
    assert called == []
    result = ping_host("2001:db8::1", 1)
    assert result.success and result.method == "icmp"
    assert called[0][-1] == "2001:db8::1"
    assert "-6" in called[0]


def test_tcp_fallback_is_identified_not_mislabeled_icmp(monkeypatch):
    monkeypatch.setattr("forgekit.services.network_service.shutil.which", lambda _: None)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(socket, "create_connection", lambda address, timeout: Connection())
    result = ping_host("127.0.0.1", count=2)
    assert result.success and result.method == "tcp" and result.packets_received == 2


def test_http_cli_errors_are_valid_json(monkeypatch):
    monkeypatch.setattr(
        requests, "get", lambda *args, **kw: (_ for _ in ()).throw(requests.Timeout("secret"))
    )
    result = CliRunner().invoke(app, ["net", "http", "https://example.test?token=secret", "--json"])
    assert result.exit_code == 1
    assert json.loads(result.output)["error"]
    assert "secret" not in result.output
