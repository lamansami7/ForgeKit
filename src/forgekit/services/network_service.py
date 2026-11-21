"""Network services."""

import contextlib
import re
import socket
import subprocess
import time

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

SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization"}


def ping_host(host: str, count: int = 4, timeout: int = 5) -> PingResult:
    # Resolve first
    resolved_ip: str | None = None
    try:
        resolved_ip = socket.gethostbyname(host)
    except socket.gaierror as e:
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
            error=f"DNS resolution failed: {e}",
        )

    # Use system ping if available, else TCP fallback
    ping_bin = None
    import shutil

    ping_bin = shutil.which("ping")

    rtts: list[float] = []
    packets_received = 0

    if ping_bin:
        try:
            cmd = [ping_bin, "-c", str(count), "-W", str(timeout), host]
            # On macOS ping uses different args but -c works; -W vs -t
            # Try to handle: if ping fails with unsupported option, fallback
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout + count * 2 + 5
            )
            output = result.stdout + result.stderr

            # Parse rtts: look for time=XX ms
            for m in re.finditer(r"time[=<]\s*([\d.]+)\s*ms", output):
                with contextlib.suppress(ValueError):
                    rtts.append(float(m.group(1)))

            # Parse packet stats: e.g. "4 packets transmitted, 4 received" or "4 packets transmitted, 4 packets received"
            mt = re.search(r"(\d+)\s+packets transmitted.*?(\d+)\s+.*received", output, re.DOTALL)
            packets_received = int(mt.group(2)) if mt else len(rtts)

            loss = 0.0
            ml = re.search(r"(\d+(?:\.\d+)?)%\s+packet loss", output)
            if ml:
                loss = float(ml.group(1))
            else:
                loss = (1 - packets_received / count) * 100 if count else 100

            success = packets_received > 0
            avg = sum(rtts) / len(rtts) if rtts else None

            return PingResult(
                host=host,
                resolved_ip=resolved_ip,
                packets_sent=count,
                packets_received=packets_received,
                packet_loss_percent=round(loss, 1),
                rtts=[round(x, 2) for x in rtts],
                avg_ms=round(avg, 2) if avg is not None else None,
                min_ms=round(min(rtts), 2) if rtts else None,
                max_ms=round(max(rtts), 2) if rtts else None,
                success=success,
                error=None if success else "No reply received",
            )
        except Exception:
            # fallback to TCP
            pass

    # TCP fallback: attempt socket connect to port 80/443 and measure
    tcp_rtts: list[float] = []
    tcp_ok = 0
    for i in range(count):
        start = time.monotonic()
        try:
            with socket.create_connection((host, 80), timeout=timeout):
                elapsed = (time.monotonic() - start) * 1000
                tcp_rtts.append(elapsed)
                tcp_ok += 1
        except OSError:
            try:
                start2 = time.monotonic()
                with socket.create_connection((host, 443), timeout=timeout):
                    elapsed = (time.monotonic() - start2) * 1000
                    tcp_rtts.append(elapsed)
                    tcp_ok += 1
            except OSError:
                pass
        if i < count - 1:
            time.sleep(0.2)

    avg = sum(tcp_rtts) / len(tcp_rtts) if tcp_rtts else None
    return PingResult(
        host=host,
        resolved_ip=resolved_ip,
        packets_sent=count,
        packets_received=tcp_ok,
        packet_loss_percent=round((1 - tcp_ok / count) * 100, 1) if count else 100,
        rtts=[round(x, 2) for x in tcp_rtts],
        avg_ms=round(avg, 2) if avg else None,
        min_ms=round(min(tcp_rtts), 2) if tcp_rtts else None,
        max_ms=round(max(tcp_rtts), 2) if tcp_rtts else None,
        success=tcp_ok > 0,
        error=None
        if tcp_ok > 0
        else "TCP connect failed (ping binary unavailable and TCP fallback failed)",
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
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    headers_sent = {"User-Agent": "ForgeKit/0.1.0"}
    start = time.monotonic()
    try:
        resp = requests.get(url, headers=headers_sent, timeout=timeout, allow_redirects=True)
        elapsed_ms = (time.monotonic() - start) * 1000

        # Redact sensitive headers
        safe_headers: dict[str, str] = {}
        for k, v in resp.headers.items():
            if k.lower() in SENSITIVE_HEADERS:
                safe_headers[k] = "***redacted***"
            else:
                safe_headers[k] = v

        # TLS info — requests doesn't expose easily; try to get from response
        tls_version = None
        try:
            # urllib3 connection info not exposed; leave None
            pass
        except Exception:
            pass

        return HttpResult(
            url=url,
            status_code=resp.status_code,
            reason=resp.reason,
            elapsed_ms=round(elapsed_ms, 1),
            final_url=resp.url if resp.url != url else None,
            redirected=len(resp.history) > 0,
            tls_version=tls_version,
            headers=safe_headers,
            error=None,
        )
    except requests.exceptions.RequestException as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return HttpResult(
            url=url,
            status_code=None,
            reason=None,
            elapsed_ms=round(elapsed_ms, 1),
            final_url=None,
            redirected=False,
            tls_version=None,
            headers=None,
            error=str(e),
        )


def get_ports() -> list[PortInfo]:
    results: list[PortInfo] = []
    try:
        conns = psutil.net_connections(kind="inet")
        for c in conns:
            if c.status != psutil.CONN_LISTEN:
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
    except (psutil.AccessDenied, PermissionError):
        # Fallback: try reading /proc/net/tcp etc? Return empty with note handled by caller
        pass
    except Exception:
        pass
    # Sort by port
    results.sort(key=lambda x: x.local_port)
    return results


def get_interfaces() -> list[InterfaceInfo]:
    interfaces: list[InterfaceInfo] = []
    try:
        addrs = psutil.net_if_addrs()
        stats = psutil.net_if_stats()
        io_counters = psutil.net_io_counters(pernic=True)
    except Exception:
        return interfaces

    for name, addr_list in addrs.items():
        stat = stats.get(name)
        is_up = stat.isup if stat else False
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

    # Local network: gateway-ish check via localhost
    # 1. DNS resolution
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
            requests.get(url, timeout=timeout)
            latency = (time.monotonic() - start) * 1000
            checks.append(
                ConnectivityCheck(name=f"HTTPS {url}", success=True, latency_ms=round(latency, 1))
            )
        except Exception as e:
            checks.append(
                ConnectivityCheck(name=f"HTTPS {url}", success=False, latency_ms=None, error=str(e))
            )

    return checks
