"""Backup toolkit."""

from pathlib import Path

import typer

from forgekit.output import create_table, get_console, print_json
from forgekit.services.backup_service import (
    create_backup,
    list_archive,
    restore_archive,
    verify_archive,
)
from forgekit.utils import format_bytes

app = typer.Typer(help="Backup and restore tools.", no_args_is_help=True)
console = get_console()


@app.command("create")
def create_cmd(
    source: str = typer.Argument(..., help="Source file or directory to back up"),
    destination: str = typer.Argument(..., help="Destination file or directory"),
    compression: str = typer.Option(
        "gz", "--compression", "-c", help="Compression: gz, bz2, xz, none"
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show what would be done without creating archive"
    ),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Create a backup archive."""
    if compression not in ("gz", "bz2", "xz", "none"):
        console.print("[red]Compression must be one of: gz, bz2, xz, none[/red]")
        raise typer.Exit(1)

    src = Path(source).resolve()
    dst = Path(destination).resolve() if not dry_run else Path(destination)

    if not src.exists():
        console.print(f"[red]Source not found: {src}[/red]")
        raise typer.Exit(1)

    if dry_run:
        result = create_backup(src, dst, compression=compression, dry_run=True)
        if json:
            print_json(result)
            return
        console.print(
            f"[cyan]Dry run:[/cyan] Would back up {result['source']} → {result['archive']}"
        )
        console.print(
            f"Estimated size: {format_bytes(result['estimated_size'])}  Files: {result['file_count']}"
        )
        return

    console.print(f"[dim]Creating backup: {src} → {dst} ({compression})...[/dim]")
    try:
        result = create_backup(src, dst, compression=compression)
    except FileExistsError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Backup failed: {e}[/red]")
        raise typer.Exit(1)

    if json:
        print_json(result)
        return

    console.print(f"[green]✓ Backup created: {result['archive']}[/green]")
    console.print(
        f"  Files: {result['file_count']}  Size: {format_bytes(result['archive_size'])} (original {format_bytes(result['total_bytes'])})  Time: {result['elapsed_seconds']}s"
    )
    console.print("[dim]Source files were preserved (never deleted).[/dim]")


@app.command("list")
def list_cmd(
    archive: str = typer.Argument(..., help="Archive path"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List contents of a backup archive."""
    p = Path(archive).resolve()
    if not p.exists():
        console.print(f"[red]Archive not found: {p}[/red]")
        raise typer.Exit(1)

    try:
        members = list_archive(p)
    except Exception as e:
        console.print(f"[red]Failed to list archive: {e}[/red]")
        raise typer.Exit(1)

    if json:
        print_json(members)
        return

    table = create_table(title=f"Archive: {p} ({len(members)} entries)")
    table.add_column("Name", style="cyan")
    table.add_column("Size", style="white", justify="right")
    table.add_column("Type", style="dim")
    table.add_column("Mode", style="dim")
    for m in members[:100]:
        table.add_row(
            m["name"][:80],
            format_bytes(m["size"]) if not m["is_dir"] else "—",
            "dir" if m["is_dir"] else "file",
            m["mode"],
        )  # type: ignore
    console.print(table)
    if len(members) > 100:
        console.print(f"[dim]... and {len(members) - 100} more entries[/dim]")


@app.command("verify")
def verify_cmd(
    archive: str = typer.Argument(..., help="Archive path"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Verify archive integrity."""
    p = Path(archive).resolve()
    if not p.exists():
        console.print(f"[red]Archive not found: {p}[/red]")
        raise typer.Exit(1)

    console.print(f"[dim]Verifying {p}...[/dim]")
    result = verify_archive(p)
    if json:
        print_json(result)
        return

    if result["valid"]:
        console.print(
            f"[green]✓ Archive is valid — {result['member_count']} members — sha256: {str(result.get('sha256', ''))[:16]}...[/green]"
        )
    else:
        console.print(f"[red]✗ Archive is invalid: {result.get('errors')}[/red]")
        raise typer.Exit(1)


@app.command("restore")
def restore_cmd(
    archive: str = typer.Argument(..., help="Archive path"),
    destination: str = typer.Argument(..., help="Restore destination directory"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would happen"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing files"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Restore a backup archive."""
    p = Path(archive).resolve()
    dst = Path(destination).resolve()

    if not p.exists():
        console.print(f"[red]Archive not found: {p}[/red]")
        raise typer.Exit(1)

    if dry_run:
        result = restore_archive(p, dst, dry_run=True, overwrite=force)
        if json:
            print_json(result)
            return
        console.print(
            f"[cyan]Dry run:[/cyan] Would restore {p} → {dst} ({result['total_members']} members)"
        )
        if result.get("would_overwrite"):
            console.print(
                f"[yellow]Would overwrite: {len(result['would_overwrite'])} files[/yellow]"
            )  # type: ignore
            for f in result["would_overwrite"][:10]:  # type: ignore
                console.print(f"  • {f}")
        return

    # Check conflicts first
    preview = restore_archive(p, dst, dry_run=True, overwrite=False)
    conflicts = preview.get("would_overwrite") or []
    if conflicts and not force:
        console.print(f"[yellow]⚠ {len(conflicts)} files would be overwritten:[/yellow]")
        for f in conflicts[:10]:
            console.print(f"  • {f}")
        console.print(
            f"[red]Refusing to overwrite. Use --force to proceed. Destination: {dst}[/red]"
        )
        # Offer to show dry-run info
        if not json:
            console.print("[dim]Use --dry-run to preview or --force to overwrite.[/dim]")
        raise typer.Exit(1)

    # Confirm unless --force or --json (non-interactive)
    if not force and not json:
        # Only prompt if interactive
        import sys

        if sys.stdin.isatty():
            typer.confirm(f"Restore {p} to {dst}?", abort=True)

    console.print(f"[dim]Restoring {p} → {dst}...[/dim]")
    try:
        result = restore_archive(p, dst, dry_run=False, overwrite=force or not conflicts)
    except Exception as e:
        console.print(f"[red]Restore failed: {e}[/red]")
        raise typer.Exit(1)

    if json:
        print_json(result)
        return

    console.print(f"[green]✓ Restored {result['total_members']} entries to {dst}[/green]")
