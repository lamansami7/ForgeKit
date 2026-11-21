"""ForgeKit CLI entrypoint."""

import logging
import os

import typer

from forgekit.cli_errors import JsonErrorGroup, explicit_json_requested
from forgekit.commands.backup import app as backup_app
from forgekit.commands.config_command import app as config_app
from forgekit.commands.dashboard import app as dashboard_app
from forgekit.commands.developer import app as dev_app
from forgekit.commands.doctor import app as doctor_app
from forgekit.commands.files import app as files_app
from forgekit.commands.git import app as git_app
from forgekit.commands.info import app as info_app
from forgekit.commands.network import app as net_app
from forgekit.commands.packages import app as packages_app
from forgekit.commands.security import app as security_app

# Import command apps
from forgekit.commands.system import app as system_app
from forgekit.commands.workspace import app as workspace_app
from forgekit.constants import APP_VERSION, BANNER, BANNER_SUBTITLE
from forgekit.output import get_console, get_err_console

console = get_console()

app = typer.Typer(
    cls=JsonErrorGroup,
    name="forge",
    help="ForgeKit — A powerful modular toolkit for Linux, developers & system diagnostics.",
    add_completion=False,
    no_args_is_help=False,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["-h", "--help"]},
)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"ForgeKit version {APP_VERSION}")
        raise typer.Exit()


def _global_banner() -> None:
    console.print(BANNER)
    console.print(BANNER_SUBTITLE)
    console.print()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool | None = typer.Option(
        None,
        "--version",
        "-V",
        help="Show version and exit",
        callback=version_callback,
        is_eager=True,
    ),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON where supported"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    config_path: str | None = typer.Option(None, "--config", help="Custom config file path"),
    no_color: bool = typer.Option(False, "--no-color", help="Disable terminal colors"),
) -> None:
    from pathlib import Path

    from forgekit.config import get_config
    from forgekit.exceptions import ConfigError
    from forgekit.output import print_json

    ctx.obj = {"json": json_output, "verbose": verbose, "config_path": config_path}
    try:
        cfg = get_config(Path(config_path) if config_path else None)
        ctx.obj["config"] = cfg
    except ConfigError as exc:
        ctx.obj["config_error"] = str(exc)
        cfg = None
        if ctx.invoked_subcommand not in ("config", "doctor"):
            if json_output or explicit_json_requested():
                print_json({"error": str(exc)})
            else:
                typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(1)
    effective_json = json_output or (cfg is not None and cfg.general.output_format == "json")
    ctx.obj["json"] = effective_json
    logging.getLogger("forgekit").setLevel(
        logging.DEBUG
        if verbose
        else getattr(logging, cfg.general.log_level)
        if cfg
        else logging.WARNING
    )
    console.no_color = (
        no_color
        or bool(os.environ.get("NO_COLOR"))
        or (cfg is not None and (not cfg.general.colors or cfg.general.output_format == "plain"))
    )
    get_err_console().no_color = console.no_color
    # Click/Typer passes nested default maps down the command tree.  This makes
    # the global flag and configured defaults effective for leaf commands too.
    defaults = dict(ctx.default_map or {})
    for group in app.registered_groups:
        values = dict(defaults.get(group.name, {}))
        if effective_json:
            values["json"] = True
        if verbose and group.name == "doctor":
            values["verbose"] = True
        for command in group.typer_instance.registered_commands:
            leaf = dict(values.get(command.name, {}))
            if effective_json:
                leaf["json"] = True
            if cfg is not None:
                if group.name == "net" and command.name == "ping":
                    leaf["timeout"] = cfg.network.ping_timeout
                if group.name == "net" and command.name in ("http", "check"):
                    leaf["timeout"] = cfg.network.http_timeout
                if group.name == "files" and command.name == "large":
                    leaf["threshold"] = cfg.files.large_threshold_mb
                if group.name == "backup" and command.name == "create":
                    leaf["compression"] = cfg.backup.compression
            values[command.name] = leaf
        defaults[group.name] = values
    ctx.default_map = defaults
    if ctx.invoked_subcommand is None:
        if effective_json:
            from forgekit.services.system_service import get_system_summary

            print_json(get_system_summary().to_dict())
            return
        # Show banner + help overview
        _global_banner()
        # Show system summary quickly
        from forgekit.services.system_service import get_system_summary
        from forgekit.utils import format_bytes, format_duration

        try:
            summary = get_system_summary()
            console.print(
                f"[bold]Host:[/bold] {summary.hostname}  [dim]•[/dim]  [bold]OS:[/bold] {summary.os_name} {summary.kernel}  [dim]•[/dim]  [bold]Arch:[/bold] {summary.architecture}"
            )
            console.print(
                f"[bold]Uptime:[/bold] {(format_duration(summary.uptime_seconds) if summary.uptime_seconds is not None else 'unavailable')}  [dim]•[/dim]  [bold]Python:[/bold] {summary.python_version}  [dim]•[/dim]  [bold]User:[/bold] {summary.user}"
            )
            if summary.cpu:
                console.print(
                    f"[bold]CPU:[/bold] {summary.cpu.model[:60]} ({summary.cpu.logical_cores or 'unavailable'} threads) {summary.cpu.usage_percent:.1f}%"
                )
            if summary.memory:
                console.print(
                    f"[bold]Memory:[/bold] {format_bytes(summary.memory.used)}/{format_bytes(summary.memory.total)} ({summary.memory.percent:.0f}%)"
                )
        except (OSError, RuntimeError) as exc:
            typer.echo(f"System summary unavailable: {exc}", err=True)

        console.print("\n[bold cyan]Available commands:[/bold cyan]")
        commands = [
            ("system", "System diagnostics — cpu, memory, disk, processes"),
            ("net", "Network toolkit — ping, dns, check, ports, interfaces, http"),
            ("git", "Git toolkit — status, history, branches, inspect"),
            ("files", "Filesystem — large, search, size, empty, duplicates"),
            ("packages", "Package manager detection & updates"),
            ("dev", "Developer environment checks"),
            ("security", "Security diagnostics (non-invasive)"),
            ("backup", "Backup — create, list, verify, restore"),
            ("workspace", "Project scaffolding — create, templates, inspect"),
            ("doctor", "Self-diagnostics"),
            ("dashboard", "Live system dashboard"),
            ("config", "Configuration — show, init, validate, get, set"),
            ("info", "About ForgeKit"),
        ]
        for name, desc in commands:
            console.print(f"  [cyan]{name:<12}[/cyan] {desc}")
        console.print(
            "\n[dim]Run `forge <command> --help` for details. `forge --help` for options.[/dim]"
        )
        console.print(
            "[dim]Example: forge system cpu  •  forge net ping google.com  •  forge doctor[/dim]"
        )


# Register subcommands
app.add_typer(system_app, name="system", help="System diagnostics")
app.add_typer(net_app, name="net", help="Network diagnostics")
app.add_typer(git_app, name="git", help="Git toolkit")
app.add_typer(files_app, name="files", help="Filesystem tools")
app.add_typer(packages_app, name="packages", help="Package management info")
app.add_typer(dev_app, name="dev", help="Developer environment")
app.add_typer(security_app, name="security", help="Security diagnostics")
app.add_typer(backup_app, name="backup", help="Backup & restore")
app.add_typer(workspace_app, name="workspace", help="Workspace scaffolding")
app.add_typer(doctor_app, name="doctor", help="Self-diagnostics")
app.add_typer(dashboard_app, name="dashboard", help="Live dashboard")
app.add_typer(info_app, name="info", help="About ForgeKit")
app.add_typer(config_app, name="config", help="Configuration")

if __name__ == "__main__":
    app()
