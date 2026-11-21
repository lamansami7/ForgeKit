"""Doctor command — self-diagnostics."""

import importlib.metadata as importlib_metadata
import platform
import shutil
import sys
from pathlib import Path

import typer

from forgekit.config import get_config
from forgekit.constants import DEFAULT_CONFIG_FILE
from forgekit.output import create_table, get_console, print_json
from forgekit.platform import get_platform_info, is_root

app = typer.Typer(help="Diagnose ForgeKit installation and environment.")
console = get_console()


@app.callback(invoke_without_command=True)
def doctor_main(
    ctx: typer.Context,
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
) -> None:
    # Always run checks; callback handles both `forge doctor` and subcommands if any
    _run_doctor(json, verbose)


def _run_doctor(as_json: bool, verbose: bool) -> None:
    checks: list[dict[str, str]] = []

    # 1. Python version
    py_ver = platform.python_version()
    major, minor = sys.version_info[:2]
    if (major, minor) >= (3, 11):
        checks.append(
            {
                "name": "Python version",
                "status": "pass",
                "message": f"Python {py_ver} OK (>=3.11)",
                "fix": "",
            }
        )
    else:
        checks.append(
            {
                "name": "Python version",
                "status": "fail",
                "message": f"Python {py_ver} — requires >=3.11",
                "fix": "Install Python 3.11 or newer",
            }
        )

    # 2. Installation integrity
    try:
        ver = importlib_metadata.version("forgekit")
        checks.append(
            {
                "name": "Installation",
                "status": "pass",
                "message": f"forgekit {ver} installed",
                "fix": "",
            }
        )
    except importlib_metadata.PackageNotFoundError:
        # Try dev install (not installed via pip)
        if Path(__file__).resolve().exists():
            checks.append(
                {
                    "name": "Installation",
                    "status": "warn",
                    "message": "Running from source (not pip installed)",
                    "fix": "pip install -e .  or  pip install .",
                }
            )
        else:
            checks.append(
                {
                    "name": "Installation",
                    "status": "fail",
                    "message": "forgekit not installed",
                    "fix": "pip install .",
                }
            )

    # 3. Dependencies
    for dep in ("typer", "rich", "psutil", "requests"):
        try:
            import importlib

            importlib.import_module(dep)
            checks.append(
                {
                    "name": f"Dependency: {dep}",
                    "status": "pass",
                    "message": f"{dep} available",
                    "fix": "",
                }
            )
        except ImportError:
            checks.append(
                {
                    "name": f"Dependency: {dep}",
                    "status": "fail",
                    "message": f"{dep} missing",
                    "fix": f"pip install {dep}",
                }
            )

    # 4. Config validity
    cfg = get_config()
    errors = cfg.validate()
    if not errors:
        checks.append(
            {
                "name": "Configuration",
                "status": "pass",
                "message": f"Config valid ({DEFAULT_CONFIG_FILE} {'exists' if DEFAULT_CONFIG_FILE.exists() else 'using defaults'})",
                "fix": "",
            }
        )
    else:
        checks.append(
            {
                "name": "Configuration",
                "status": "fail",
                "message": f"Config errors: {'; '.join(errors)}",
                "fix": f"Edit {DEFAULT_CONFIG_FILE} or run: forge config init",
            }
        )

    # 5. PATH
    forge_path = shutil.which("forge")
    if forge_path:
        checks.append(
            {"name": "PATH", "status": "pass", "message": f"forge in PATH: {forge_path}", "fix": ""}
        )
    else:
        # Check if running via python -m
        checks.append(
            {
                "name": "PATH",
                "status": "warn",
                "message": "forge not in PATH (may be running via python -m forgekit)",
                "fix": "Ensure ~/.local/bin or venv bin is in PATH, or reinstall",
            }
        )

    # 6. Platform support
    plat = get_platform_info()
    if plat.is_linux:
        checks.append(
            {
                "name": "Platform",
                "status": "pass",
                "message": f"Linux {plat.release} {plat.machine} — fully supported",
                "fix": "",
            }
        )
    elif plat.is_macos:
        checks.append(
            {
                "name": "Platform",
                "status": "warn",
                "message": f"macOS {plat.release} — supported with limitations",
                "fix": "",
            }
        )
    elif plat.is_windows:
        checks.append(
            {
                "name": "Platform",
                "status": "warn",
                "message": "Windows — experimental support",
                "fix": "",
            }
        )
    else:
        checks.append(
            {
                "name": "Platform",
                "status": "warn",
                "message": f"Unknown platform: {plat.system}",
                "fix": "",
            }
        )

    # 7. Permissions
    if is_root():
        checks.append(
            {
                "name": "Permissions",
                "status": "warn",
                "message": "Running as root — not recommended",
                "fix": "Run as regular user",
            }
        )
    else:
        checks.append(
            {
                "name": "Permissions",
                "status": "pass",
                "message": "Running as regular user",
                "fix": "",
            }
        )

    # 8. Optional tools
    for tool in ("git", "ping", "curl"):
        if shutil.which(tool):
            checks.append(
                {
                    "name": f"Optional: {tool}",
                    "status": "pass",
                    "message": f"{tool} available",
                    "fix": "",
                }
            )
        else:
            checks.append(
                {
                    "name": f"Optional: {tool}",
                    "status": "info",
                    "message": f"{tool} not found (optional)",
                    "fix": f"Install {tool} for full functionality",
                }
            )

    # 9. Config file exists
    if DEFAULT_CONFIG_FILE.exists():
        checks.append(
            {
                "name": "Config file",
                "status": "pass",
                "message": f"Found: {DEFAULT_CONFIG_FILE}",
                "fix": "",
            }
        )
    else:
        checks.append(
            {
                "name": "Config file",
                "status": "info",
                "message": "No config file — using defaults",
                "fix": "Run: forge config init",
            }
        )

    # Output
    if as_json:
        print_json(checks)
        return

    table = create_table(title="ForgeKit Doctor")
    table.add_column("Status", style="cyan")
    table.add_column("Check", style="white")
    table.add_column("Message", style="white")
    table.add_column("Fix", style="dim")

    status_styles = {"pass": "green", "warn": "yellow", "fail": "red", "info": "blue"}
    status_icons = {"pass": "✓", "warn": "⚠", "fail": "✗", "info": "ℹ"}

    for c in checks:
        style = status_styles.get(c["status"], "white")
        icon = status_icons.get(c["status"], "•")
        table.add_row(
            f"[{style}]{icon} {c['status'].upper()}[/{style}]",
            c["name"],
            c["message"][:90],
            c["fix"][:60],
        )

    console.print(table)

    # Summary
    fails = sum(1 for c in checks if c["status"] == "fail")
    warns = sum(1 for c in checks if c["status"] == "warn")
    passes = sum(1 for c in checks if c["status"] == "pass")

    if fails:
        console.print(f"\n[red]✗ {fails} failure(s) — action required[/red]")
        raise typer.Exit(1)
    elif warns:
        console.print(
            f"\n[yellow]⚠ {warns} warning(s), {passes} passed — ForgeKit should work with minor limitations[/yellow]"
        )
    else:
        console.print(f"\n[green]✓ All checks passed ({passes} checks)[/green]")

    if verbose:
        console.print(
            f"\n[dim]Verbose: Python {py_ver} | Platform {plat.system} | Config: {DEFAULT_CONFIG_FILE}[/dim]"
        )
