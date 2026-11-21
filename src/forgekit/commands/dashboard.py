"""Interactive dashboard."""

import math
import time

import typer
from rich.live import Live

from forgekit.config import get_config
from forgekit.output import cli_error, get_console
from forgekit.services.system_service import (
    get_processes,
    get_system_summary,
)
from forgekit.utils import format_bytes, format_duration

app = typer.Typer(help="Live system dashboard.")
console = get_console()


@app.callback(invoke_without_command=True)
def dashboard_main(
    ctx: typer.Context,
    refresh: float | None = typer.Option(
        None, "--refresh", "-r", help="Refresh interval in seconds (0.5-60)"
    ),
    json: bool = typer.Option(False, "--json", help="Output snapshot as JSON and exit"),
) -> None:
    if ctx.invoked_subcommand is None:
        _run_dashboard(refresh, json, ctx.find_root().obj["config"])


def _run_dashboard(refresh: float | None, as_json: bool, cfg=None) -> None:
    cfg = cfg or get_config()
    interval = refresh if refresh is not None else cfg.dashboard.refresh_interval
    if interval is None:
        interval = 2.0
    # Validate
    if not math.isfinite(interval) or interval < 0.5 or interval > 60:
        cli_error("Refresh interval must be between 0.5 and 60 seconds", as_json)

    if as_json:
        # Snapshot
        summary = get_system_summary()
        from forgekit.output import print_json

        print_json(summary.to_dict())
        return

    # Live dashboard
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    def make_view() -> Panel:
        summary = get_system_summary()
        procs = get_processes(limit=5, sort_by="cpu") if cfg.dashboard.show_processes else []

        # Build content

        # Header
        Text(" ForgeKit Dashboard ", style="bold white on cyan")
        # We'll use tables for sections

        # System
        sys_table = Table(show_header=False, box=None, padding=(0, 1))
        sys_table.add_column("k", style="cyan")
        sys_table.add_column("v", style="white")
        sys_table.add_row("Host", summary.hostname)
        sys_table.add_row("OS", f"{summary.os_name} {summary.kernel}")
        sys_table.add_row(
            "Uptime",
            (
                format_duration(summary.uptime_seconds)
                if summary.uptime_seconds is not None
                else "unavailable"
            ),
        )
        sys_table.add_row("User", summary.user)
        if summary.load_avg:
            sys_table.add_row(
                "Load",
                f"{summary.load_avg[0]:.2f} {summary.load_avg[1]:.2f} {summary.load_avg[2]:.2f}",
            )

        # CPU
        cpu = summary.cpu
        cpu_table = Table(show_header=False, box=None, padding=(0, 1))
        cpu_table.add_column("k", style="cyan")
        cpu_table.add_column("v", style="white")
        if cpu:
            color = (
                "red"
                if cpu.usage_percent >= 80
                else "green"
                if cpu.usage_percent < 50
                else "yellow"
            )
            cpu_table.add_row("Model", cpu.model[:50])
            cpu_table.add_row("Cores", f"{cpu.physical_cores} / {cpu.logical_cores} threads")
            cpu_table.add_row("Usage", f"[{color}]{cpu.usage_percent:.1f}%[/{color}]")
            if cpu.per_core_percent:
                # bar
                bars = []
                for v in cpu.per_core_percent[:8]:
                    c = "red" if v >= 80 else "yellow" if v >= 50 else "green"
                    bars.append(f"[{c}]█[/{c}] {v:.0f}%")
                cpu_table.add_row("Per-core", "  ".join(bars))
        else:
            cpu_table.add_row("CPU", "[dim]unavailable[/dim]")

        # Memory
        mem = summary.memory
        mem_table = Table(show_header=False, box=None, padding=(0, 1))
        mem_table.add_column("k", style="cyan")
        mem_table.add_column("v", style="white")
        if mem:
            color = "red" if mem.percent >= 85 else "yellow" if mem.percent >= 60 else "green"
            mem_table.add_row(
                "RAM",
                f"{format_bytes(mem.used)} / {format_bytes(mem.total)} [{color}]{mem.percent:.1f}%[/{color}]",
            )
            mem_table.add_row(
                "Swap",
                f"{format_bytes(mem.swap_used)} / {format_bytes(mem.swap_total)} {mem.swap_percent:.0f}%",
            )
        else:
            mem_table.add_row("Memory", "[dim]unavailable[/dim]")

        # Disk
        disk_table = Table(show_header=False, box=None, padding=(0, 1))
        disk_table.add_column("k", style="cyan")
        disk_table.add_column("v", style="white")
        if summary.disk and summary.disk.partitions:
            for p in summary.disk.partitions[:4]:
                color = "red" if p.percent >= 95 else "yellow" if p.percent >= 85 else "green"
                disk_table.add_row(
                    p.mountpoint,
                    f"{format_bytes(p.used)}/{format_bytes(p.total)} [{color}]{p.percent:.0f}%[/{color}] {p.fstype}",
                )
        else:
            disk_table.add_row("Disk", "[dim]unavailable[/dim]")

        # Processes
        proc_table = Table(title="Top Processes (CPU)", show_header=True, header_style="bold cyan")
        proc_table.add_column("PID", style="dim", justify="right")
        proc_table.add_column("Name", style="white")
        proc_table.add_column("CPU%", style="yellow", justify="right")
        proc_table.add_column("MEM%", style="magenta", justify="right")
        for p in procs:
            proc_table.add_row(
                str(p.pid),
                p.name[:25],
                f"{p.cpu_percent:.1f}" if p.cpu_percent is not None else "—",
                f"{p.memory_percent:.1f}" if p.memory_percent is not None else "—",
            )

        from rich.console import Group

        sections = [
            Text(f"ForgeKit Dashboard — refresh: {interval}s — Ctrl+C to exit", style="bold cyan"),
            Text(""),
            Panel(sys_table, title="System", border_style="cyan"),
            Panel(cpu_table, title="CPU", border_style="cyan"),
            Panel(mem_table, title="Memory", border_style="cyan"),
            Panel(disk_table, title="Disk", border_style="cyan"),
        ]
        if cfg.dashboard.show_network:
            import psutil

            try:
                io = psutil.net_io_counters()
                text = (
                    f"Received: {format_bytes(io.bytes_recv)}  Sent: {format_bytes(io.bytes_sent)}"
                    if io
                    else "unavailable"
                )
            except (OSError, NotImplementedError, psutil.Error):
                text = "unavailable"
            sections.append(Panel(text, title="Network (cumulative)", border_style="cyan"))
        if cfg.dashboard.show_processes:
            sections.append(proc_table)
        group = Group(*sections)
        return Panel(group, title="ForgeKit", border_style="cyan", padding=(1, 2))

    # Redirected/non-interactive output must not run forever.
    if not console.is_terminal:
        console.print(make_view())
        return

    # Run loop
    console.print(f"[dim]Starting dashboard (refresh {interval}s) — Press Ctrl+C to exit[/dim]")
    try:
        with Live(make_view(), console=console, auto_refresh=False, screen=False) as live:
            while True:
                start = time.monotonic()
                live.update(make_view(), refresh=True)
                time.sleep(max(0.05, interval - (time.monotonic() - start)))
    except KeyboardInterrupt:
        console.print("\n[dim]Dashboard exited.[/dim]")
