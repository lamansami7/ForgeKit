"""Config command."""

from pathlib import Path

import typer

from forgekit.config import ForgeConfig, ensure_default_config, get_config
from forgekit.constants import DEFAULT_CONFIG_FILE
from forgekit.output import create_table, get_console, print_json

app = typer.Typer(help="Manage ForgeKit configuration.", no_args_is_help=True)
console = get_console()


@app.command("show")
def show_cmd(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
    path: str | None = typer.Option(None, "--path", help="Config file path"),
) -> None:
    """Show current configuration."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_FILE
    cfg = get_config(cfg_path if path else None)

    if json:
        print_json(cfg.to_dict())
        return

    console.print(
        f"[bold]Config file:[/bold] {cfg_path} {'[green](exists)[/green]' if cfg_path.exists() else '[dim](not found — using defaults)[/dim]'}"
    )

    table = create_table(title="Configuration")
    table.add_column("Section", style="cyan")
    table.add_column("Key", style="white")
    table.add_column("Value", style="white")

    d = cfg.to_dict()
    for section, values in d.items():
        for k, v in values.items():  # type: ignore
            table.add_row(section, k, str(v))

    console.print(table)


@app.command("init")
def init_cmd(
    force: bool = typer.Option(False, "--force", help="Overwrite existing config"),
    path: str | None = typer.Option(None, "--path", help="Config file path"),
) -> None:
    """Create default configuration file."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_FILE
    if cfg_path.exists() and not force:
        console.print(
            f"[yellow]Config already exists: {cfg_path} (use --force to overwrite)[/yellow]"
        )
        raise typer.Exit(1)

    p = ensure_default_config() if not path else Path(path)
    if path:
        # Write default manually
        from forgekit.config import DEFAULT_CONFIG_TOML

        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(DEFAULT_CONFIG_TOML)
        console.print(f"[green]✓ Config created: {p}[/green]")
    else:
        console.print(f"[green]✓ Config created: {p}[/green]")


@app.command("validate")
def validate_cmd(
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
    path: str | None = typer.Option(None, "--path", help="Config file path"),
) -> None:
    """Validate configuration."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_FILE
    cfg = get_config(cfg_path if path else None)
    errors = cfg.validate()

    if json:
        print_json({"valid": len(errors) == 0, "errors": errors, "path": str(cfg_path)})
        return

    if not errors:
        console.print(f"[green]✓ Configuration valid: {cfg_path}[/green]")
    else:
        console.print(f"[red]✗ Configuration invalid: {cfg_path}[/red]")
        for e in errors:
            console.print(f"  [red]•[/red] {e}")
        raise typer.Exit(1)


@app.command("get")
def get_cmd(
    key: str = typer.Argument(..., help="Config key (e.g. dashboard.refresh_interval)"),
    path: str | None = typer.Option(None, "--path", help="Config file path"),
) -> None:
    """Get a config value."""
    cfg = get_config(Path(path) if path else None)
    d = cfg.to_dict()
    # Support dot notation
    parts = key.split(".")
    cur = d
    for part in parts:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]  # type: ignore
        else:
            console.print(f"[red]Key not found: {key}[/red]")
            raise typer.Exit(1)
    console.print(f"{key} = {cur}")


@app.command("set")
def set_cmd(
    key: str = typer.Argument(..., help="Config key (e.g. dashboard.refresh_interval)"),
    value: str = typer.Argument(..., help="New value"),
    path: str | None = typer.Option(None, "--path", help="Config file path"),
) -> None:
    """Set a config value."""
    cfg_path = Path(path) if path else DEFAULT_CONFIG_FILE
    cfg = get_config(cfg_path if path else None)
    d = cfg.to_dict()
    parts = key.split(".")
    if len(parts) != 2:
        console.print(
            "[red]Key must be in format section.key (e.g. dashboard.refresh_interval)[/red]"
        )
        raise typer.Exit(1)
    section, k = parts
    if section not in d or k not in d[section]:
        console.print(f"[red]Unknown key: {key}[/red]")
        raise typer.Exit(1)

    # Type coercion based on current value
    current = d[section][k]
    try:
        if isinstance(current, bool):
            if value.lower() in ("true", "1", "yes"):
                new_val: object = True
            elif value.lower() in ("false", "0", "no"):
                new_val = False
            else:
                raise ValueError("Boolean must be true/false")
        elif isinstance(current, int):
            new_val = int(value)
        elif isinstance(current, float):
            new_val = float(value)
        elif isinstance(current, list):
            # Expect comma-separated
            new_val = [x.strip() for x in value.split(",")]
        else:
            new_val = value
    except ValueError as e:
        console.print(f"[red]Invalid value: {e}[/red]")
        raise typer.Exit(1)

    d[section][k] = new_val  # type: ignore
    # Recreate config
    new_cfg = ForgeConfig.from_dict(d)
    errors = new_cfg.validate()
    if errors:
        console.print(f"[red]Validation failed: {'; '.join(errors)}[/red]")
        raise typer.Exit(1)

    new_cfg.save(cfg_path)
    console.print(f"[green]✓ Set {key} = {new_val} → {cfg_path}[/green]")


@app.command("path")
def path_cmd() -> None:
    """Show config file path."""
    console.print(str(DEFAULT_CONFIG_FILE))
    console.print(f"[dim]Exists: {DEFAULT_CONFIG_FILE.exists()}[/dim]")
