"""Package manager commands."""

import typer

from forgekit.output import cli_error, create_table, get_console, print_json
from forgekit.services.package_service import (
    check_updates_generic,
    detect_managers,
    list_installed_packages,
    primary_manager,
)

app = typer.Typer(help="Package manager detection and info.", no_args_is_help=False)
console = get_console()


@app.callback(invoke_without_command=True)
def packages_main(
    ctx: typer.Context,
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    if ctx.invoked_subcommand is None:
        _show_packages(json)


def _show_packages(as_json: bool) -> None:
    managers = detect_managers()
    if as_json:
        print_json({"managers": managers, "primary": managers[0] if managers else None})
        return

    if not managers:
        console.print("[yellow]No supported package managers detected.[/yellow]")
        console.print("[dim]Supported: apt, dnf, yum, pacman, zypper, apk, brew[/dim]")
        return

    table = create_table(title="Detected Package Managers")
    table.add_column("Manager", style="cyan")
    table.add_column("Path", style="white")
    table.add_column("Version", style="white")
    table.add_column("Update Command", style="dim")
    for m in managers:
        primary = " [bold green](primary)[/bold green]" if m == managers[0] else ""
        table.add_row(
            m["name"] + primary,
            m["path"] or "—",
            (m["version"] or "—")[:60],
            m["update_cmd"] or "—",
        )
    console.print(table)

    # Show update info for primary
    prim = managers[0] if managers else None
    if prim:
        console.print(f"\n[dim]Primary: {prim['name']} — to update: {prim['update_cmd']}[/dim]")
        console.print(
            "[dim]ForgeKit never auto-installs or updates packages. Run the command above manually.[/dim]"
        )


@app.command("list")
def list_cmd(
    manager: str | None = typer.Option(None, "--manager", "-m", help="Package manager name"),
    limit: int = typer.Option(20, "--limit", "-n", help="Limit results", min=1, max=100),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List installed packages (where supported)."""
    prim = primary_manager()
    mgr = manager or (prim["name"] if prim else None)
    if not mgr:
        cli_error("No package manager detected. Use --manager to specify.", json)

    try:
        pkgs = list_installed_packages(mgr, limit=limit)
    except (ValueError, OSError, RuntimeError) as exc:
        if json:
            print_json({"error": str(exc)})
        else:
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    if json:
        print_json({"manager": mgr, "packages": pkgs})
        return

    if not pkgs:
        console.print(f"[yellow]Could not list packages for {mgr} or no packages found.[/yellow]")
        return

    table = create_table(title=f"Installed Packages ({mgr}) — showing {len(pkgs)}")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Package", style="white")
    for i, p in enumerate(pkgs, 1):
        table.add_row(str(i), p[:120])
    console.print(table)


@app.command("updates")
def updates_cmd(
    manager: str | None = typer.Option(None, "--manager", "-m", help="Package manager"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Check for available updates."""
    prim = primary_manager()
    mgr = manager or (prim["name"] if prim else None)
    if not mgr:
        cli_error("No package manager detected.", json)

    info = check_updates_generic(mgr)
    if json:
        print_json(info)
        if not info.get("available"):
            raise typer.Exit(1)
        return

    if not info.get("available"):
        console.print(
            f"[yellow]{info.get('error') or info.get('note') or 'Update status unavailable'}[/yellow]"
        )
        raise typer.Exit(1)
    if info.get("upgradable_count") is not None:
        console.print(f"[bold]Upgradable: {info['upgradable_count']}[/bold]")
        if info.get("upgradable"):
            for u in info["upgradable"][:10]:
                console.print(f"  • {u}")
    else:
        console.print(f"[dim]{info.get('note', 'No update info available')}[/dim]")
        if prim:
            console.print(f"[dim]Run manually: {prim['update_cmd']}[/dim]")


@app.command("info")
def info_cmd(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Detailed package manager info."""
    _show_packages(json)
