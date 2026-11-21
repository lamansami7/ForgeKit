"""Network services."""

import ipaddress
import platform
import re
import shutil
import socket
import subprocess
import time
from urllib.parse import urljoin, urlsplit

import psutil
import requests

from forgekit.models.network_info import (
    ConnectivityCheck,
    DnsResult,
    HttpResult,
    InterfaceInfo,
    PingResult,
    PortInfo,
)
from forgekit.utils import is_valid_hostname, redact_url

SENSITIVE_HEADERS = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
    "x-auth-token",
    "authentication-info",
    "proxy-authenticate",
    "www-authenticate",
}


def ping_host(host: str, count: int = 4, timeout: int = 5) -> PingResult:
    if not is_valid_hostname(host) or count < 1 or timeout < 1:
        return PingResult(
            host=host,
            resolved_ip=None,
            packets_sent=0,
            packets_received=0,
            packet_loss_percent=100.0,
            rtts=[],
            avg_ms=None,
            min_ms=None,
            max_ms=None,
            success=False,
            error="Invalid host, count or timeout",
        )
    try:
        # Numeric addresses bypass the system resolver; hostnames may return IPv6.
        try:
            resolved = str(ipaddress.ip_address(host))
        except ValueError:
            infos = socket.getaddrinfo(host, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
            if not infos:
                raise OSError("No addresses returned")
            resolved = infos[0][4][0]
    except OSError as exc:
        return PingResult(
            host=host,
            resolved_ip=None,
            packets_sent=count,
            packets_received=0,
            packet_loss_percent=100.0,
            rtts=[],
            avg_ms=None,
            min_ms=None,
            max_ms=None,
            success=False,
            error=f"DNS resolution failed: {exc}",
        )
    binary = shutil.which("ping")
    if binary:
        system = platform.system()
        if system == "Windows":
            cmd = [binary, "-n", str(count), "-w", str(timeout * 1000), resolved]
        else:
            wait = timeout * 1000 if system == "Darwin" else timeout
            cmd = [binary, "-c", str(count), "-W", str(wait)]
            if ":" in resolved:
                cmd.append("-6")
            cmd.append(resolved)
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=count * (timeout + 1) + 5
            )
            output = result.stdout + result.stderr
            rtts = [float(m.group(1)) for m in re.finditer(r"time[=<]\s*([\d.]+)\s*ms", output)]
            stats = re.search(
                r"(\d+)\s+packets transmitted.*?(\d+)\s+(?:packets\s+)?received",
                output,
                re.DOTALL | re.IGNORECASE,
            )
            if not stats and system == "Windows":
                stats_windows = re.search(r"Received\s*=\s*(\d+)", output, re.IGNORECASE)
                received = int(stats_windows.group(1)) if stats_windows else len(rtts)
            else:
                received = int(stats.group(2)) if stats else len(rtts)
            received = min(count, received)
            return PingResult(
                host=host,
                resolved_ip=resolved,
                packets_sent=count,
                packets_received=received,
                packet_loss_percent=round((1 - received / count) * 100, 1),
                rtts=[round(x, 2) for x in rtts],
                avg_ms=round(sum(rtts) / len(rtts), 2) if rtts else None,
                min_ms=round(min(rtts), 2) if rtts else None,
                max_ms=round(max(rtts), 2) if rtts else None,
                success=received > 0,
                error=None if received else "No ICMP reply received",
                method="icmp",
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return PingResult(
                host=host,
                resolved_ip=resolved,
                packets_sent=count,
                packets_received=0,
                packet_loss_percent=100.0,
                rtts=[],
                avg_ms=None,
                min_ms=None,
                max_ms=None,
                success=False,
                error=f"Ping failed: {exc}",
                method="icmp",
            )
    # Explicitly identify the TCP fallback; it is not an ICMP measurement.
    rtts = []
    for _ in range(count):
        for port in (80, 443):
            start = time.monotonic()
            try:
                with socket.create_connection((resolved, port), timeout=timeout):
                    rtts.append((time.monotonic() - start) * 1000)
                    break
            except OSError:
                continue
    return PingResult(
        host=host,
        resolved_ip=resolved,
        packets_sent=count,
        packets_received=len(rtts),
        packet_loss_percent=round((1 - len(rtts) / count) * 100, 1),
        rtts=[round(x, 2) for x in rtts],
        avg_ms=round(sum(rtts) / len(rtts), 2) if rtts else None,
        min_ms=round(min(rtts), 2) if rtts else None,
        max_ms=round(max(rtts), 2) if rtts else None,
        success=bool(rtts),
        error=None if rtts else "TCP fallback failed (ports 80 and 443)",
        method="tcp",
    )


def resolve_dns(domain: str) -> DnsResult:
    ipv4: list[str] = []
    ipv6: list[str] = []
    error: str | None = None
    cname: str | None = None

    # Use socket.getaddrinfo
    try:
        infos = socket.getaddrinfo(domain, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for family, _, _, canon, sockaddr in infos:
            ip = sockaddr[0]
            if family == socket.AF_INET:
                if ip not in ipv4:
                    ipv4.append(ip)
            elif family == socket.AF_INET6 and ip not in ipv6:
                ipv6.append(ip)
            if canon and canon != domain:
                cname = canon
    except socket.gaierror as e:
        error = str(e)
    except Exception as e:
        error = str(e)

    return DnsResult(domain=domain, ipv4=ipv4, ipv6=ipv6, cname=cname, error=error)


def check_http(url: str, timeout: int = 10) -> HttpResult:
    if "://" not in url:
        url = "https://" + url
    display_url = redact_url(url)
    start = time.monotonic()
    redirected = False
    current = url
    try:
        if timeout < 1:
            raise ValueError("Timeout must be positive")
        for attempt in range(6):
            parsed = urlsplit(current)
            if (
                parsed.scheme not in ("http", "https")
                or not parsed.hostname
                or parsed.username is not None
                or parsed.password is not None
                or any(ord(char) < 32 for char in current)
            ):
                raise ValueError("Expected an HTTP(S) URL without embedded credentials")
            try:
                _ = parsed.port
            except ValueError as exc:
                raise ValueError("Invalid URL port") from exc
            # Manual redirects avoid requests reading unbounded redirect bodies.
            response = requests.get(
                current,
                headers={"User-Agent": "ForgeKit/0.1.0"},
                timeout=timeout,
                allow_redirects=False,
                stream=True,
            )
            try:
                location = response.headers.get("Location")
                if response.status_code in (301, 302, 303, 307, 308) and location:
                    if attempt == 5:
                        raise ValueError("Too many HTTP redirects")
                    current = urljoin(current, location)
                    redirected = True
                    continue
                safe_headers = {}
                for key, value in response.headers.items():
                    lower = key.lower()
                    if lower in SENSITIVE_HEADERS or any(
                        term in lower
                        for term in (
                            "token",
                            "secret",
                            "api-key",
                            "api_key",
                            "apikey",
                            "password",
                            "cookie",
                            "authorization",
                        )
                    ):
                        safe_headers[key] = "***redacted***"
                    elif lower in ("location", "content-location"):
                        safe_headers[key] = redact_url(value)
                    else:
                        safe_headers[key] = value
                return HttpResult(
                    url=display_url,
                    status_code=response.status_code,
                    reason=response.reason,
                    elapsed_ms=round((time.monotonic() - start) * 1000, 1),
                    final_url=redact_url(current) if redirected else None,
                    redirected=redirected,
                    tls_version=None,
                    headers=safe_headers,
                    error=None,
                )
            finally:
                response.close()
        raise ValueError("Too many HTTP redirects")
    except (requests.exceptions.RequestException, ValueError) as exc:
        # Exception messages from requests can contain credentials and query values.
        message = (
            str(exc) if isinstance(exc, ValueError) else f"{type(exc).__name__}: request failed"
        )
        return HttpResult(
            url=display_url,
            status_code=None,
            reason=None,
            elapsed_ms=round((time.monotonic() - start) * 1000, 1),
            final_url=None,
            redirected=redirected,
            tls_version=None,
            headers=None,
            error=message,
        )


def get_ports() -> list[PortInfo]:
    results: list[PortInfo] = []
    try:
        conns = psutil.net_connections(kind="inet")
        for c in conns:
            if c.type == socket.SOCK_STREAM and c.status != psutil.CONN_LISTEN:
                continue
            if c.type not in (socket.SOCK_STREAM, socket.SOCK_DGRAM):
                continue
            laddr = c.laddr
            if not laddr:
                continue
            ip, port = laddr[0], laddr[1]
            proto = (
                "tcp"
                if c.type == socket.SOCK_STREAM
                else "udp"
                if c.type == socket.SOCK_DGRAM
                else str(c.type)
            )
            # Try to get process
            pid = c.pid
            proc_name: str | None = None
            if pid:
                try:
                    p = psutil.Process(pid)
                    proc_name = p.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    proc_name = None
            results.append(
                PortInfo(
                    proto=proto,
                    local_addr=ip,
                    local_port=port,
                    state=c.status,
                    pid=pid,
                    process=proc_name,
                )
            )
    except (psutil.AccessDenied, PermissionError, OSError, NotImplementedError) as exc:
        raise RuntimeError(f"Cannot inspect local ports: {exc}") from exc
    # Sort by port
    results.sort(key=lambda x: x.local_port)
    return results


def get_interfaces() -> list[InterfaceInfo]:
    interfaces: list[InterfaceInfo] = []
    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        io_counters = psutil.net_io_counters(pernic=True)
    except (psutil.Error, OSError, NotImplementedError) as exc:
        raise RuntimeError(f"Cannot inspect network interfaces: {exc}") from exc

    for name, addr_list in addrs.items():
        stat = stats.get(name)
        is_up = stat.isup if stat else None
        mtu = stat.mtu if stat else None

        ipv4: list[str] = []
        ipv6: list[str] = []
        mac: str | None = None

        for a in addr_list:
            if a.family == socket.AF_INET:
                ipv4.append(a.address)
            elif a.family == socket.AF_INET6:
                ipv6.append(a.address.split("%")[0])
            elif a.family == psutil.AF_LINK:  # type: ignore
                mac = a.address

        io = io_counters.get(name) if io_counters else None

        interfaces.append(
            InterfaceInfo(
                name=name,
                is_up=is_up,
                mtu=mtu,
                ipv4=ipv4,
                ipv6=ipv6,
                mac=mac,
                bytes_sent=io.bytes_sent if io else None,
                bytes_recv=io.bytes_recv if io else None,
                packets_sent=io.packets_sent if io else None,
                packets_recv=io.packets_recv if io else None,
            )
        )
    interfaces.sort(key=lambda x: x.name)
    return interfaces


def check_connectivity(timeout: int = 5) -> list[ConnectivityCheck]:
    checks: list[ConnectivityCheck] = []

    # 1. DNS resolution (this does not probe a local gateway)
    start = time.monotonic()
    try:
        socket.gethostbyname("google.com")
        latency = (time.monotonic() - start) * 1000
        checks.append(
            ConnectivityCheck(
                name="DNS resolution (google.com)", success=True, latency_ms=round(latency, 1)
            )
        )
    except Exception as e:
        checks.append(
            ConnectivityCheck(
                name="DNS resolution (google.com)", success=False, latency_ms=None, error=str(e)
            )
        )

    # 2. HTTPS connectivity
    for url in ["https://1.1.1.1", "https://google.com"]:
        start = time.monotonic()
        try:
            result = check_http(url, timeout=timeout)
            if result.error:
                raise OSError(result.error)
            latency = (time.monotonic() - start) * 1000
            checks.append(
                ConnectivityCheck(name=f"HTTPS {url}", success=True, latency_ms=round(latency, 1))
            )
        except Exception as e:
            checks.append(
                ConnectivityCheck(name=f"HTTPS {url}", success=False, latency_ms=None, error=str(e))
            )

    return checks
