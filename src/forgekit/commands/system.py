"""System commands."""

import typer

from forgekit.constants import (
    CPU_WARNING_THRESHOLD,
    DISK_CRITICAL_THRESHOLD,
    DISK_WARNING_THRESHOLD,
    MEMORY_WARNING_THRESHOLD,
)
from forgekit.output import create_panel, create_table, get_console, print_json
from forgekit.services.system_service import (
    get_cpu_info,
    get_disk_info,
    get_memory_info,
    get_processes,
    get_system_summary,
)
from forgekit.utils import format_bytes, format_duration

app = typer.Typer(help="System diagnostics and information.", no_args_is_help=False)
console = get_console()


@app.callback(invoke_without_command=True)
def system_main(
    ctx: typer.Context,
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    if ctx.invoked_subcommand is None:
        # Show system summary
        summary = get_system_summary()
        if json:
            print_json(summary.to_dict())
            return
        _show_summary(summary)


def _show_summary(summary) -> None:

    console.print(
        create_panel(
            f"[bold]Host:[/bold] {summary.hostname}  [dim]•[/dim]  [bold]OS:[/bold] {summary.os_name} {summary.kernel}  [dim]•[/dim]  [bold]Arch:[/bold] {summary.architecture}",
            title="System Summary",
            style="cyan",
        )
    )
    console.print(
        f"[bold]User:[/bold] {summary.user}  [dim]•[/dim]  [bold]Python:[/bold] {summary.python_version}  [dim]•[/dim]  [bold]Uptime:[/bold] {format_duration(summary.uptime_seconds)}"
    )
    if summary.load_avg:
        console.print(
            f"[bold]Load avg:[/bold] {summary.load_avg[0]:.2f}, {summary.load_avg[1]:.2f}, {summary.load_avg[2]:.2f}"
        )
    if summary.battery_percent is not None:
        plug = "🔌" if summary.battery_plugged else "🔋"
        console.print(f"[bold]Battery:[/bold] {plug} {summary.battery_percent:.0f}%")

    if summary.cpu:
        console.print(
            f"\n[bold cyan]CPU:[/bold cyan] {summary.cpu.model} ({summary.cpu.physical_cores} cores, {summary.cpu.logical_cores} threads) — {summary.cpu.usage_percent:.1f}%"
        )
        if summary.cpu.frequency_current_mhz:
            console.print(f"  Frequency: {summary.cpu.frequency_current_mhz:.0f} MHz")
    if summary.memory:
        console.print(
            f"[bold cyan]Memory:[/bold cyan] {format_bytes(summary.memory.used)} / {format_bytes(summary.memory.total)} ({summary.memory.percent:.1f}%)  Swap: {format_bytes(summary.memory.swap_used)} / {format_bytes(summary.memory.swap_total)}"
        )
    if summary.disk:
        for p in summary.disk.partitions:
            bar = "█" * int(p.percent / 10) + "░" * (10 - int(p.percent / 10))
            color = (
                "red"
                if p.percent >= DISK_CRITICAL_THRESHOLD
                else "yellow"
                if p.percent >= DISK_WARNING_THRESHOLD
                else "green"
            )
            console.print(
                f"[bold cyan]Disk {p.mountpoint}:[/bold cyan] {format_bytes(p.used)} / {format_bytes(p.total)} [{bar}] {p.percent:.0f}% [{color}]{p.fstype}[/{color}]"
            )


@app.command("cpu")
def cpu_cmd(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
    per_core: bool = typer.Option(False, "--per-core", help="Show per-core usage"),
) -> None:
    """Show CPU information."""
    info = get_cpu_info()
    if json:
        print_json(info.to_dict())
        return

    table = create_table(title="CPU Information")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Model", info.model)
    table.add_row("Architecture", info.architecture)
    table.add_row("Physical cores", str(info.physical_cores))
    table.add_row("Logical processors", str(info.logical_cores))
    usage_color = (
        "red"
        if info.usage_percent >= CPU_WARNING_THRESHOLD
        else "green"
        if info.usage_percent < 50
        else "yellow"
    )
    table.add_row("Usage", f"[{usage_color}]{info.usage_percent:.1f}%[/{usage_color}]")
    if info.frequency_current_mhz:
        table.add_row("Frequency (current)", f"{info.frequency_current_mhz:.0f} MHz")
        if info.frequency_min_mhz and info.frequency_max_mhz:
            table.add_row(
                "Frequency (min/max)",
                f"{info.frequency_min_mhz:.0f} / {info.frequency_max_mhz:.0f} MHz",
            )
    console.print(table)

    if per_core or info.per_core_percent:
        ctable = create_table(title="Per-core Usage")
        ctable.add_column("Core", style="cyan")
        ctable.add_column("Usage", style="white")
        for i, v in enumerate(info.per_core_percent):
            color = "red" if v >= 80 else "yellow" if v >= 50 else "green"
            ctable.add_row(f"Core {i}", f"[{color}]{v:.1f}%[/{color}]")
        console.print(ctable)

    if info.usage_percent >= CPU_WARNING_THRESHOLD:
        console.print(f"[yellow]⚠ High CPU usage: {info.usage_percent:.1f}%[/yellow]")


@app.command("memory")
def memory_cmd(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show memory information."""
    info = get_memory_info()
    if json:
        print_json(info.to_dict())
        return

    table = create_table(title="Memory")
    table.add_column("Type", style="cyan")
    table.add_column("Total", style="white")
    table.add_column("Used", style="white")
    table.add_column("Available/Free", style="white")
    table.add_column("Usage", style="white")

    color = (
        "red"
        if info.percent >= MEMORY_WARNING_THRESHOLD
        else "green"
        if info.percent < 60
        else "yellow"
    )
    table.add_row(
        "RAM",
        format_bytes(info.total),
        format_bytes(info.used),
        format_bytes(info.available),
        f"[{color}]{info.percent:.1f}%[/{color}]",
    )
    swap_color = "yellow" if info.swap_percent > 50 else "green"
    table.add_row(
        "Swap",
        format_bytes(info.swap_total),
        format_bytes(info.swap_used),
        format_bytes(info.swap_free),
        f"[{swap_color}]{info.swap_percent:.1f}%[/{swap_color}]",
    )
    console.print(table)

    if info.percent >= MEMORY_WARNING_THRESHOLD:
        console.print(f"[yellow]⚠ High memory usage: {info.percent:.1f}%[/yellow]")
    if info.swap_percent > 80:
        console.print(f"[yellow]⚠ High swap usage: {info.swap_percent:.1f}%[/yellow]")


@app.command("disk")
def disk_cmd(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show disk usage."""
    info = get_disk_info()
    if json:
        print_json(info.to_dict())
        return

    if not info.partitions:
        console.print("[yellow]No disk partitions found or accessible.[/yellow]")
        return

    table = create_table(title="Disk Usage")
    table.add_column("Device", style="cyan")
    table.add_column("Mount", style="white")
    table.add_column("Type", style="dim")
    table.add_column("Total", style="white")
    table.add_column("Used", style="white")
    table.add_column("Free", style="white")
    table.add_column("Use%", style="white")

    for p in info.partitions:
        color = (
            "red"
            if p.percent >= DISK_CRITICAL_THRESHOLD
            else "yellow"
            if p.percent >= DISK_WARNING_THRESHOLD
            else "green"
        )
        table.add_row(
            p.device,
            p.mountpoint,
            p.fstype,
            format_bytes(p.total),
            format_bytes(p.used),
            format_bytes(p.free),
            f"[{color}]{p.percent:.0f}%[/{color}]",
        )

    console.print(table)
    for p in info.partitions:
        if p.percent >= DISK_CRITICAL_THRESHOLD:
            console.print(f"[red]⛔ Critical: {p.mountpoint} at {p.percent:.0f}%[/red]")
        elif p.percent >= DISK_WARNING_THRESHOLD:
            console.print(f"[yellow]⚠ Warning: {p.mountpoint} at {p.percent:.0f}%[/yellow]")


@app.command("processes")
def processes_cmd(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
    limit: int = typer.Option(
        10, "--limit", "-n", help="Number of processes to show", min=1, max=50
    ),
    sort: str = typer.Option("cpu", "--sort", help="Sort by: cpu or memory"),
) -> None:
    """Show top processes."""
    if sort not in ("cpu", "memory"):
        console.print("[red]Error: --sort must be 'cpu' or 'memory'[/red]")
        raise typer.Exit(1)

    procs = get_processes(limit=limit, sort_by=sort)
    if json:
        print_json([p.to_dict() for p in procs])
        return

    table = create_table(title=f"Top {limit} Processes by {sort.upper()}")
    table.add_column("PID", style="cyan", justify="right")
    table.add_column("Name", style="white")
    table.add_column("User", style="dim")
    table.add_column("CPU%", style="yellow", justify="right")
    table.add_column("MEM%", style="magenta", justify="right")
    table.add_column("RSS", style="white", justify="right")
    table.add_column("Status", style="dim")

    for p in procs:
        table.add_row(
            str(p.pid),
            p.name[:30],
            p.username or "-",
            f"{p.cpu_percent:.1f}",
            f"{p.memory_percent:.1f}",
            format_bytes(p.memory_rss),
            p.status,
        )

    console.print(table)
    console.print(
        "[dim]Note: ForgeKit never terminates processes automatically. Use system tools to manage processes.[/dim]"
    )
