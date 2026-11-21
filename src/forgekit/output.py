"""Output helpers — Rich rendering and JSON."""

import json
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

_console = Console()
_err_console = Console(stderr=True)


def get_console() -> Console:
    return _console


def get_err_console() -> Console:
    return _err_console


def print_error(message: str) -> None:
    _err_console.print(f"[bold red]Error:[/bold red] {message}")


def print_json(data: Any, pretty: bool = True) -> None:
    """Print JSON without Rich formatting."""
    text = json.dumps(data, indent=2 if pretty else None, default=str, ensure_ascii=False)
    # Use plain print to avoid Rich markup interfering
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def should_use_json(json_flag: bool, config_json: bool = False) -> bool:
    return json_flag or config_json


def create_table(title: str | None = None, show_header: bool = True) -> Table:
    t = Table(title=title, show_header=show_header, header_style="bold cyan", title_justify="left")
    t.show_lines = False
    return t


def create_panel(content: Any, title: str | None = None, style: str = "cyan") -> Panel:
    return Panel(content, title=title, border_style=style, padding=(0, 1))


def cli_error(message: str, as_json: bool = False, exit_code: int = 1) -> None:
    """Emit a command failure in the selected format and stop execution."""
    import typer

    if as_json:
        print_json({"error": message})
    else:
        print_error(message)
    raise typer.Exit(exit_code)
