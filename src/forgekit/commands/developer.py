"""Developer toolkit."""

import typer

from forgekit.output import create_table, get_console, print_json
from forgekit.services.developer_service import detect_all, path_diagnostics

app = typer.Typer(help="Developer environment checks.", no_args_is_help=False)
console = get_console()


@app.callback(invoke_without_command=True)
def dev_main(
    ctx: typer.Context,
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    if ctx.invoked_subcommand is None:
        _show_summary(json)


def _show_summary(as_json: bool) -> None:
    tools = detect_all()
    path_issues = path_diagnostics()

    if as_json:
        print_json({"tools": tools, "path": path_issues})
        return

    table = create_table(title="Developer Tools")
    table.add_column("Tool", style="cyan")
    table.add_column("Found", style="white")
    table.add_column("Version", style="white")
    table.add_column("Path", style="dim")

    for t in tools:
        found = "[green]✓[/green]" if t["found"] else "[red]✗[/red]"
        ver = (t["version"] or "—")[:60] if t["found"] else t.get("details", "missing") or "missing"  # type: ignore
        path = t["path"] or "—"  # type: ignore
        table.add_row(str(t["name"]), found, str(ver), str(path))

    console.print(table)

    # PATH diagnostics
    ptable = create_table(title="PATH Diagnostics")
    ptable.add_column("Level", style="cyan")
    ptable.add_column("Message", style="white")
    ptable.add_column("Fix", style="dim")
    for iss in path_issues:
        level_style = {"pass": "green", "warn": "yellow", "fail": "red", "info": "blue"}.get(
            iss["level"], "white"
        )
        ptable.add_row(
            f"[{level_style}]{iss['level'].upper()}[/{level_style}]",
            iss["message"],
            iss.get("fix", ""),
        )
    console.print(ptable)


@app.command("check")
def check_cmd(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Run environment checks."""
    _show_summary(json)


@app.command("versions")
def versions_cmd(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show versions of detected tools."""
    tools = detect_all()
    if json:
        print_json([t for t in tools if t["found"]])
        return

    table = create_table(title="Tool Versions")
    table.add_column("Tool", style="cyan")
    table.add_column("Version", style="white")
    for t in tools:
        if t["found"]:
            table.add_row(str(t["name"]), str(t["version"] or "unknown")[:80])
    console.print(table)
    missing = [t["name"] for t in tools if not t["found"]]
    if missing:
        console.print(f"[dim]Missing: {', '.join(str(m) for m in missing)}[/dim]")
        console.print(
            "[dim]Install missing tools via your package manager or official installers. ForgeKit never auto-installs.[/dim]"
        )
