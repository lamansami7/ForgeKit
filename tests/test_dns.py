"""DNS specific tests."""

import socket

from forgekit.services.network_service import resolve_dns


def test_resolve_localhost():
    r = resolve_dns("localhost")
    assert r.domain == "localhost"
    # Should have at least one address or error
    assert r.ipv4 is not None
    assert r.ipv6 is not None


def test_resolve_invalid(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *args: (_ for _ in ()).throw(socket.gaierror("not found"))
    )
    r = resolve_dns("invalid.invalid.invalid.invalid")
    assert r.error is not None or (not r.ipv4 and not r.ipv6)
