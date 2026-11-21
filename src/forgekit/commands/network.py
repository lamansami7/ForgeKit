"""Network commands."""

import typer

from forgekit.output import create_table, get_console, print_json
from forgekit.services.network_service import (
    check_connectivity,
    check_http,
    get_interfaces,
    get_ports,
    ping_host,
    resolve_dns,
)
from forgekit.utils import format_bytes

app = typer.Typer(help="Network diagnostics toolkit.", no_args_is_help=False)
console = get_console()


@app.callback(invoke_without_command=True)
def net_main(
    ctx: typer.Context,
    json: bool = typer.Option(False, "--json", help="Output local network overview as JSON"),
) -> None:
    """Show local interfaces and bound sockets without making network requests."""
    if ctx.invoked_subcommand is not None:
        return
    try:
        interfaces = get_interfaces()
        ports = get_ports()
    except RuntimeError as exc:
        if json:
            print_json({"error": str(exc)})
        else:
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    if json:
        print_json(
            {"interfaces": [i.to_dict() for i in interfaces], "ports": [p.to_dict() for p in ports]}
        )
    else:
        console.print(f"Interfaces: {len(interfaces)}  Bound TCP/UDP sockets: {len(ports)}")
        console.print("Use forge net interfaces or forge net ports for details.")


@app.command("ping")
def ping_cmd(
    host: str = typer.Argument(..., help="Hostname or IP to ping"),
    count: int = typer.Option(4, "--count", "-c", help="Number of pings", min=1, max=20),
    timeout: int = typer.Option(5, "--timeout", "-t", help="Timeout in seconds", min=1, max=30),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Test connectivity to a host."""
    result = ping_host(host, count=count, timeout=timeout)
    if json:
        print_json(result.to_dict())
        if not result.success:
            raise typer.Exit(1)
        return
    console.print(f"[dim]Pinging {host} ({count} packets)...[/dim]")

    if result.error and not result.success:
        console.print(f"[red]✗ {result.error}[/red]")
        if result.resolved_ip:
            console.print(f"Resolved IP: {result.resolved_ip}")

    else:
        table = create_table(
            title=f"Ping {host}" + (f" ({result.resolved_ip})" if result.resolved_ip else "")
        )
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")
        table.add_row("Method", result.method.upper())
        table.add_row("Host", result.host)
        table.add_row("Resolved IP", result.resolved_ip or "—")
        table.add_row("Sent / Received", f"{result.packets_sent} / {result.packets_received}")
        table.add_row("Packet loss", f"{result.packet_loss_percent:.1f}%")
        if result.rtts:
            table.add_row("RTTs (ms)", ", ".join(f"{x:.1f}" for x in result.rtts))
            table.add_row(
                "Min / Avg / Max (ms)",
                f"{result.min_ms:.1f} / {result.avg_ms:.1f} / {result.max_ms:.1f}",
            )
        console.print(table)
        if result.success:
            console.print("[green]✓ Host is reachable[/green]")
        else:
            console.print("[red]✗ Host unreachable[/red]")
    if not result.success:
        raise typer.Exit(1)


@app.command("dns")
def dns_cmd(
    domain: str = typer.Argument(..., help="Domain to resolve"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
    timeout: int = typer.Option(5, "--timeout", help="Resolution timeout seconds", min=1, max=60),
) -> None:
    """Resolve DNS for a domain."""
    result = resolve_dns(domain, timeout=timeout)
    if json:
        print_json(result.to_dict())
        if result.error:
            raise typer.Exit(1)
        return

    if result.error:
        console.print(f"[red]✗ DNS resolution failed for {domain}: {result.error}[/red]")
        raise typer.Exit(1)

    table = create_table(title=f"DNS: {domain}")
    table.add_column("Type", style="cyan")
    table.add_column("Values", style="white")
    if result.ipv4:
        table.add_row("IPv4 (A)", ", ".join(result.ipv4))
    else:
        table.add_row("IPv4 (A)", "[dim]none[/dim]")
    if result.ipv6:
        table.add_row("IPv6 (AAAA)", ", ".join(result.ipv6))
    else:
        table.add_row("IPv6 (AAAA)", "[dim]none[/dim]")
    if result.cname:
        table.add_row("CNAME", result.cname)
    console.print(table)
    if result.ipv4 or result.ipv6:
        console.print("[green]✓ Resolved successfully[/green]")


@app.command("check")
def check_cmd(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
    timeout: int = typer.Option(5, "--timeout", help="Timeout seconds", min=1, max=60),
) -> None:
    """Run internet connectivity diagnostics."""
    results = check_connectivity(timeout=timeout)
    if json:
        print_json([r.to_dict() for r in results])
        if any(not r.success for r in results):
            raise typer.Exit(1)
        return
    console.print("[dim]Checking connectivity...[/dim]")

    table = create_table(title="Connectivity Check")
    table.add_column("Check", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("Latency", style="white")
    table.add_column("Details", style="dim")

    for r in results:
        status = "[green]✓ OK[/green]" if r.success else "[red]✗ FAIL[/red]"
        latency = f"{r.latency_ms:.1f} ms" if r.latency_ms is not None else "—"
        details = r.error or ""
        table.add_row(r.name, status, latency, details[:60])

    console.print(table)
    console.print("[dim]Checks: DNS resolution + HTTPS endpoints (1.1.1.1, google.com)[/dim]")
    if any(not result.success for result in results):
        raise typer.Exit(1)


@app.command("ports")
def ports_cmd(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show local listening TCP and bound UDP sockets."""
    try:
        ports = get_ports()
    except RuntimeError as exc:
        if json:
            print_json({"error": str(exc)})
        else:
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    if json:
        print_json([p.to_dict() for p in ports])
        return

    if not ports:
        console.print(
            "[yellow]No listening ports found or permission denied. Try running with elevated privileges for complete results.[/yellow]"
        )
        console.print("[dim]Note: Some entries require root to show PID/process.[/dim]")
        return

    table = create_table(title="Listening Ports")
    table.add_column("Proto", style="cyan")
    table.add_column("Address", style="white")
    table.add_column("Port", style="yellow", justify="right")
    table.add_column("State", style="white")
    table.add_column("PID", style="dim", justify="right")
    table.add_column("Process", style="white")

    for p in ports:
        table.add_row(
            p.proto,
            p.local_addr,
            str(p.local_port),
            p.state,
            str(p.pid) if p.pid else "—",
            p.process or "—",
        )

    console.print(table)
    console.print("[dim]PID/process may be hidden without sufficient permissions.[/dim]")


@app.command("interfaces")
def interfaces_cmd(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List network interfaces."""
    try:
        ifaces = get_interfaces()
    except RuntimeError as exc:
        if json:
            print_json({"error": str(exc)})
        else:
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    if json:
        print_json([i.to_dict() for i in ifaces])
        return

    if not ifaces:
        console.print("[yellow]No network interfaces found.[/yellow]")
        return

    table = create_table(title="Network Interfaces")
    table.add_column("Interface", style="cyan")
    table.add_column("Status", style="white")
    table.add_column("IPv4", style="white")
    table.add_column("IPv6", style="dim")
    table.add_column("MAC", style="white")
    table.add_column("RX / TX", style="white")

    for iface in ifaces:
        status = (
            "[green]UP[/green]"
            if iface.is_up is True
            else "[red]DOWN[/red]"
            if iface.is_up is False
            else "unknown"
        )
        ipv4 = ", ".join(iface.ipv4) if iface.ipv4 else "—"
        ipv6 = ", ".join(iface.ipv6[:1]) if iface.ipv6 else "—"
        mac = iface.mac or "—"
        rx_tx = ""
        if iface.bytes_recv is not None and iface.bytes_sent is not None:
            rx_tx = f"{format_bytes(iface.bytes_recv)} / {format_bytes(iface.bytes_sent)}"
        else:
            rx_tx = "—"
        table.add_row(iface.name, status, ipv4, ipv6, mac, rx_tx)

    console.print(table)


@app.command("http")
def http_cmd(
    url: str = typer.Argument(..., help="URL to check (e.g. https://example.com)"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
    timeout: int = typer.Option(10, "--timeout", help="Timeout seconds", min=1, max=60),
    show_headers: bool = typer.Option(False, "--headers", help="Show response headers"),
) -> None:
    """Perform HTTP diagnostics."""
    result = check_http(url, timeout=timeout)
    if json:
        print_json(result.to_dict())
        if result.error or (result.status_code and result.status_code >= 400):
            raise typer.Exit(1)
        return
    console.print(f"[dim]Fetching {result.url}...[/dim]")

    table = create_table(title=f"HTTP: {result.url}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("URL", result.url)
    if result.final_url:
        table.add_row("Final URL", result.final_url)
    table.add_row(
        "Status",
        f"{result.status_code} {result.reason}"
        if result.status_code
        else f"[red]Error: {result.error}[/red]",
    )
    table.add_row("Redirected", "Yes" if result.redirected else "No")
    table.add_row("Time", f"{result.elapsed_ms:.1f} ms")
    if result.tls_version:
        table.add_row("TLS", result.tls_version)
    console.print(table)

    if result.status_code and 200 <= result.status_code < 400:
        console.print("[green]✓ Request succeeded[/green]")
    elif result.error:
        console.print(f"[red]✗ {result.error}[/red]")

    if show_headers and result.headers:
        htable = create_table(title="Response Headers")
        htable.add_column("Header", style="cyan")
        htable.add_column("Value", style="white")
        for k, v in result.headers.items():
            htable.add_row(k, v[:120])
        console.print(htable)

    if result.error or (result.status_code and result.status_code >= 400):
        raise typer.Exit(1)
