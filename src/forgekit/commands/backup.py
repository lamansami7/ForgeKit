"""Backup and restore commands."""

import tarfile
from pathlib import Path

import typer

from forgekit.output import create_table, get_console, print_json
from forgekit.services.backup_service import (
    RestoreError,
    create_backup,
    list_archive,
    restore_archive,
    verify_archive,
)
from forgekit.utils import format_bytes

app = typer.Typer(help="Backup and restore tools.", no_args_is_help=True)
console = get_console()


def _fail(message: str, as_json: bool) -> None:
    if as_json:
        print_json({"error": message})
    else:
        console.print(f"[red]Error: {message}[/red]")
    raise typer.Exit(1)


@app.command("create")
def create_cmd(
    ctx: typer.Context,
    source: str = typer.Argument(..., help="Source file or directory to back up"),
    destination: str | None = typer.Argument(
        None, help="Destination outside the source (defaults to configured backup directory)"
    ),
    compression: str = typer.Option(
        "gz", "--compression", "-c", help="Compression: gz, bz2, xz, none"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without creating anything"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Create a backup without modifying the source or overwriting an archive."""
    try:
        destination = destination or ctx.find_root().obj["config"].backup.default_destination
        result = create_backup(Path(source), Path(destination), compression, dry_run)
    except (OSError, ValueError, EOFError, tarfile.TarError) as exc:
        _fail(f"Backup failed: {exc}", json)
    if json:
        print_json(result)
    elif dry_run:
        console.print(f"[cyan]Dry run:[/cyan] {result['source']} → {result['archive']}")
        console.print(
            f"Estimated size: {format_bytes(result['estimated_size'])}  Files: {result['file_count']}"
        )
    else:
        console.print(f"[green]✓ Backup created: {result['archive']}[/green]")
        console.print(
            f"Files: {result['file_count']}  Archive: {format_bytes(result['archive_size'])}"
        )
        console.print(f"SHA-256: {result['manifest']['sha256']}")


@app.command("list")
def list_cmd(
    archive: str = typer.Argument(..., help="Archive path"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List the contents of an archive."""
    try:
        members = list_archive(Path(archive))
    except (OSError, ValueError, EOFError, tarfile.TarError) as exc:
        _fail(f"Failed to list archive: {exc}", json)
    if json:
        print_json(members)
        return
    table = create_table(title=f"Archive: {archive} ({len(members)} entries)")
    for name in ("Name", "Size", "Type", "Mode"):
        table.add_column(name)
    for member in members[:100]:
        table.add_row(
            str(member["name"]),
            format_bytes(member["size"]) if not member["is_dir"] else "—",
            str(member["type"]),
            str(member["mode"]),
        )
    console.print(table)
    if len(members) > 100:
        console.print(f"[dim]... and {len(members) - 100} more entries[/dim]")


@app.command("verify")
def verify_cmd(
    archive: str = typer.Argument(..., help="Archive path"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
    sha256: str | None = typer.Option(
        None, "--sha256", help="Compare with a trusted SHA-256 digest"
    ),
) -> None:
    """Read archive contents and check compression and restore safety."""
    try:
        result = verify_archive(Path(archive), expected_sha256=sha256)
    except OSError as exc:
        _fail(f"Verification failed: {exc}", json)
    if json:
        print_json(result)
    elif result["valid"]:
        console.print(f"[green]✓ Archive readable — {result['member_count']} members[/green]")
        console.print(f"SHA-256: {result['sha256']} (compare with a trusted checksum)")
    else:
        console.print(f"[red]Archive invalid or unsafe: {result['errors']}[/red]")
    if not result["valid"]:
        raise typer.Exit(1)


@app.command("restore")
def restore_cmd(
    archive: str = typer.Argument(..., help="Archive path"),
    destination: str = typer.Argument(..., help="Restore destination directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without creating anything"),
    force: bool = typer.Option(False, "--force", help="Allow overwriting existing regular files"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Restore regular files and directories; links and special files are rejected."""
    try:
        if not dry_run and not force and not json:
            import sys

            if sys.stdin.isatty():
                typer.confirm(f"Restore {archive} to {destination}?", abort=True)
        result = restore_archive(Path(archive), Path(destination), dry_run=dry_run, overwrite=force)
    except RestoreError as exc:
        if json:
            print_json(
                {
                    "error": str(exc),
                    "rolled_back": exc.rolled_back,
                    "rollback_errors": exc.rollback_errors,
                }
            )
        else:
            if exc.rolled_back:
                console.print(
                    "[yellow]Restore failed; destination rolled back to its previous state.[/yellow]"
                )
            else:
                console.print(
                    "[red]Restore failed and rollback was incomplete — inspect the destination.[/red]"
                )
            console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1)
    except (OSError, ValueError, EOFError, tarfile.TarError) as exc:
        _fail(f"Restore failed: {exc}", json)
    if json:
        print_json(result)
    elif result["status"] == "needs_confirmation":
        console.print(f"[red]{result['message']}[/red]")
        for path in result["would_overwrite"]:
            console.print(f"  • {path}")
    elif dry_run:
        console.print(
            f"[cyan]Dry run:[/cyan] {result['total_members']} entries → {result['destination']}"
        )
        console.print(f"Existing files: {result['conflict_count']}")
    else:
        console.print(
            f"[green]✓ Restored {result['restored']} entries to {result['destination']}[/green]"
        )
        if result.get("overwritten"):
            console.print(
                f"[dim]Replaced {result['overwritten']} existing file(s); originals were removed "
                "after the restore completed successfully.[/dim]"
            )
    if result["status"] == "needs_confirmation":
        raise typer.Exit(1)
