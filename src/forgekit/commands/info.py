"""Info command."""

import platform

import typer

from forgekit.constants import APP_VERSION, BANNER, BANNER_SUBTITLE
from forgekit.output import create_table, get_console, print_json

app = typer.Typer(help="Show ForgeKit information.")
console = get_console()


@app.callback(invoke_without_command=True)
def info_main(
    ctx: typer.Context,
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    _show_info(json)


def _show_info(as_json: bool) -> None:
    info = {
        "name": "ForgeKit",
        "version": APP_VERSION,
        "description": "A powerful modular command-line toolkit for Linux, developers, and system diagnostics.",
        "python": platform.python_version(),
        "platform": platform.system(),
        "license": "MIT",
        "repository": "https://github.com/lamansami7/ForgeKit",
        "author": "Sami Laman",
    }
    if as_json:
        print_json(info)
        return

    console.print(BANNER)
    console.print(BANNER_SUBTITLE)
    console.print()
    table = create_table(title="ForgeKit Info")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    for k, v in info.items():
        table.add_row(k.title(), str(v))
    console.print(table)
    console.print("\n[dim]Run `forge --help` for commands. Docs: docs/[/dim]")
