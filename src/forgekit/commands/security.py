"""Security diagnostics."""

from pathlib import Path

import typer

from forgekit.output import cli_error, create_table, get_console, print_json
from forgekit.services.security_service import check_security

app = typer.Typer(help="Security diagnostics (non-invasive).", no_args_is_help=False)
console = get_console()


@app.callback(invoke_without_command=True)
def security_main(
    ctx: typer.Context,
    path: str | None = typer.Option(None, "--path", "-p", help="Path to scan (file or dir)"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    if ctx.invoked_subcommand is None:
        _run_check(Path(path) if path else None, json)


def _run_check(target: Path | None, as_json: bool) -> None:
    p = target.resolve() if target else None
    if p and not p.exists():
        cli_error(f"Path not found: {p}", as_json)

    try:
        findings = check_security(p)
    except (OSError, ValueError) as exc:
        if as_json:
            print_json({"error": str(exc)})
        else:
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)

    if as_json:
        print_json(findings)
        return
    console.print("[dim]Running security checks (read-only, non-invasive)...[/dim]")

    table = create_table(title="Security Findings")
    table.add_column("Level", style="cyan")
    table.add_column("Check", style="white")
    table.add_column("Message", style="white")
    table.add_column("Remediation", style="dim")

    level_styles = {"pass": "green", "info": "blue", "warn": "yellow", "fail": "red"}
    for f in findings:
        lvl = f["level"]
        style = level_styles.get(lvl, "white")
        table.add_row(
            f"[{style}]{lvl.upper()}[/{style}]",
            f["check"],
            f["message"][:80],
            f.get("fix", "")[:60],
        )

    console.print(table)
    console.print(
        "\n[dim]Note: These are limited heuristic checks, not a full security audit.[/dim]"
    )
    console.print("[dim]ForgeKit does NOT claim a system is secure based on these checks.[/dim]")
    console.print(
        "[dim]No exploitation, password cracking, or intrusive tests were performed.[/dim]"
    )


@app.command("check")
def check_cmd(
    path: str | None = typer.Option(None, "--path", "-p", help="Path to scan"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Run security checks."""
    _run_check(Path(path) if path else None, json)


@app.command("scan")
def scan_cmd(
    target: str = typer.Argument(..., help="File to scan for risky patterns"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Scan a config file for risky patterns."""
    from forgekit.services.security_service import scan_risky_config

    p = Path(target)
    if not p.exists():
        cli_error(f"File not found: {p}", json)

    try:
        findings = scan_risky_config(p)
        # Also include general checks
        extra = check_security(p)
    except (OSError, ValueError) as exc:
        if json:
            print_json({"error": str(exc)})
        else:
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    # merge
    all_findings = findings + [f for f in extra if f["check"] != "config_pattern"]

    if json:
        print_json(all_findings)
        return

    if not findings:
        console.print(f"[green]No risky patterns detected in {p}[/green]")
    else:
        table = create_table(title=f"Scan: {p}")
        table.add_column("Level", style="cyan")
        table.add_column("Message", style="white")
        table.add_column("Fix", style="dim")
        for f in findings:
            style = {"warn": "yellow", "fail": "red", "info": "blue"}.get(f["level"], "white")
            table.add_row(
                f"[{style}]{f['level'].upper()}[/{style}]", f["message"], f.get("fix", "")
            )
        console.print(table)
