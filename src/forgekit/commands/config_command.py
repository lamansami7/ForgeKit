"""Inspect and safely update TOML configuration."""

from pathlib import Path

import typer

from forgekit.config import ForgeConfig, ensure_default_config, get_config, resolve_config_path
from forgekit.exceptions import ConfigError
from forgekit.output import create_table, get_console, print_json

app = typer.Typer(help="Manage ForgeKit configuration.", no_args_is_help=True)
console = get_console()


def _path(ctx: typer.Context, path: str | None = None) -> Path:
    root = ctx.find_root()
    global_path = root.obj.get("config_path") if isinstance(root.obj, dict) else None
    return resolve_config_path(path or global_path)


def _error(message: str, as_json: bool) -> None:
    if as_json:
        print_json({"error": message})
    else:
        console.print(f"[red]Error: {message}[/red]")
    raise typer.Exit(1)


def _load(path: Path, as_json: bool) -> ForgeConfig:
    try:
        return get_config(path)
    except ConfigError as exc:
        _error(str(exc), as_json)
        raise AssertionError("unreachable") from exc


@app.command("show")
def show_cmd(
    ctx: typer.Context,
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
    path: str | None = typer.Option(None, "--path", help="Config file path"),
) -> None:
    """Show current configuration, including defaults."""
    p = _path(ctx, path)
    cfg = _load(p, json)
    if json:
        print_json(cfg.to_dict())
        return
    console.print(
        f"[bold]Config file:[/bold] {p} {'(exists)' if p.exists() else '(using defaults)'}"
    )
    table = create_table(title="Configuration")
    for col in ("Section", "Key", "Value"):
        table.add_column(col)
    for section, values in cfg.to_dict().items():
        for key, value in values.items():
            table.add_row(section, key, str(value))
    console.print(table)


@app.command("init")
def init_cmd(
    ctx: typer.Context,
    force: bool = typer.Option(False, "--force", help="Explicitly replace existing config"),
    path: str | None = typer.Option(None, "--path", help="Config file path"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Create the default configuration; never overwrite without --force."""
    p = _path(ctx, path)
    try:
        ensure_default_config(p, overwrite=force)
    except ConfigError as exc:
        _error(str(exc), json)
    if json:
        print_json({"path": str(p), "created": True})
    else:
        console.print(f"[green]✓ Config created: {p}[/green]")


@app.command("validate")
def validate_cmd(
    ctx: typer.Context,
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
    path: str | None = typer.Option(None, "--path", help="Config file path"),
) -> None:
    """Validate TOML syntax, known keys, types and values."""
    p = _path(ctx, path)
    try:
        errors = ForgeConfig.load(p).validate()
    except ConfigError as exc:
        errors = [str(exc)]
    if json:
        print_json({"valid": not errors, "errors": errors, "path": str(p)})
    elif errors:
        console.print(f"[red]✗ Configuration invalid: {p}[/red]")
        for error in errors:
            console.print(f"  • {error}")
    else:
        console.print(f"[green]✓ Configuration valid: {p}[/green]")
    if errors:
        raise typer.Exit(1)


@app.command("get")
def get_cmd(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Config key (e.g. dashboard.refresh_interval)"),
    path: str | None = typer.Option(None, "--path", help="Config file path"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Get a configuration value using section.key notation."""
    value: object = _load(_path(ctx, path), json).to_dict()
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            _error(f"Key not found: {key}", json)
        value = value[part]
    if json:
        print_json({"key": key, "value": value})
    else:
        console.print(f"{key} = {value}")


@app.command("set")
def set_cmd(
    ctx: typer.Context,
    key: str = typer.Argument(..., help="Config key (e.g. dashboard.refresh_interval)"),
    value: str = typer.Argument(..., help="New value; lists are comma-separated"),
    path: str | None = typer.Option(None, "--path", help="Config file path"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Atomically update a known key while preserving TOML comments."""
    p = _path(ctx, path)
    data = _load(p, json).to_dict()
    parts = key.split(".")
    if len(parts) != 2 or parts[0] not in data or parts[1] not in data[parts[0]]:
        _error(f"Unknown key: {key}; expected section.key", json)
    section, name = parts
    current = data[section][name]
    try:
        if isinstance(current, bool):
            if value.lower() not in ("true", "false", "yes", "no", "1", "0"):
                raise ValueError("Boolean must be true or false")
            new_value: object = value.lower() in ("true", "yes", "1")
        elif isinstance(current, int):
            new_value = int(value)
        elif isinstance(current, float):
            new_value = float(value)
        elif isinstance(current, list):
            new_value = [x.strip() for x in value.split(",") if x.strip()]
        else:
            new_value = value
        data[section][name] = new_value
        config = ForgeConfig.from_dict(data)
        config.save(p)
    except (ValueError, ConfigError) as exc:
        _error(f"Invalid value: {exc}", json)
    if json:
        print_json({"key": key, "value": new_value, "path": str(p)})
    else:
        console.print(f"[green]✓ Set {key} = {new_value} → {p}[/green]")


@app.command("path")
def path_cmd(
    ctx: typer.Context,
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show the effective configuration file path."""
    p = _path(ctx)
    if json:
        print_json({"path": str(p), "exists": p.exists()})
    else:
        console.print(str(p))
        console.print(f"[dim]Exists: {p.exists()}[/dim]")
