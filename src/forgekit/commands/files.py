"""Filesystem commands."""

from pathlib import Path

import typer

from forgekit.config import get_config
from forgekit.output import create_table, get_console, print_json
from forgekit.services.filesystem_service import (
    directory_size,
    find_duplicates,
    find_empty_dirs,
    find_large_files,
    search_files,
)
from forgekit.utils import format_bytes

app = typer.Typer(help="Filesystem analysis toolkit.", no_args_is_help=True)
console = get_console()


def _exclude_dirs(ctx: typer.Context) -> set[str]:
    cfg = ctx.find_root().obj.get("config")
    if cfg is None:
        cfg = get_config()
    return set(cfg.files.exclude_dirs)


def _directory(path: str, as_json: bool) -> Path:
    root = Path(path).expanduser().resolve()
    if not root.is_dir():
        if as_json:
            print_json({"error": f"Not an accessible directory: {root}"})
        else:
            console.print(f"[red]Not an accessible directory: {root}[/red]")
        raise typer.Exit(1)
    return root


@app.command("large")
def large_cmd(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Directory to scan"),
    threshold: int = typer.Option(100, "--threshold", "-t", help="Size threshold in MB", min=0),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results", min=1, max=100),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Find large files."""
    root = _directory(path, json)

    threshold_bytes = threshold * 1024 * 1024
    results = find_large_files(
        root, threshold_bytes=threshold_bytes, exclude_dirs=_exclude_dirs(ctx), limit=limit
    )
    if json:
        print_json(results)
        return
    console.print(f"[dim]Scanning {root} for files >= {threshold} MB...[/dim]")

    if not results:
        console.print(f"[green]No files >= {threshold} MB found.[/green]")
        return

    table = create_table(title=f"Large Files (≥{threshold} MB) in {root}")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Size", style="yellow", justify="right")
    table.add_column("Path", style="white")
    for i, r in enumerate(results, 1):
        table.add_row(str(i), format_bytes(r["size"]), str(r["path"]))  # type: ignore
    console.print(table)


@app.command("search")
def search_cmd(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Directory to search"),
    query: str = typer.Argument(..., help="Search query (filename or extension)"),
    ext: bool = typer.Option(False, "--ext", help="Search by extension"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max results", min=1),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Search files by name or extension."""
    root = _directory(path, json)

    results = search_files(
        root, query, exclude_dirs=_exclude_dirs(ctx), by_extension=ext, limit=limit
    )
    if json:
        print_json(results)
        return

    if not results:
        console.print(f"[yellow]No matches for '{query}' in {root}[/yellow]")
        return

    table = create_table(title=f"Search: '{query}' in {root} ({len(results)} results)")
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="white")
    table.add_column("Size", style="dim", justify="right")
    for r in results:
        table.add_row(r["name"], r["path"], format_bytes(r["size"]) if r.get("size") else "—")  # type: ignore
    console.print(table)


@app.command("size")
def size_cmd(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Directory to analyze"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show directory size breakdown."""
    root = _directory(path, json)

    info = directory_size(root, exclude_dirs=_exclude_dirs(ctx))
    if json:
        print_json(info)
        return
    console.print(f"[dim]Analyzing {root}...[/dim]")

    console.print(f"[bold]Path:[/bold] {info['path']}")
    console.print(
        f"[bold]Total size:[/bold] {format_bytes(info['total_size'])}  [dim]•[/dim]  Files: {info['file_count']}  Dirs: {info['dir_count']}"
    )

    if info["breakdown"]:
        table = create_table(title="Contents")
        table.add_column("Name", style="cyan")
        table.add_column("Type", style="dim")
        table.add_column("Size", style="white", justify="right")
        table.add_column("Path", style="dim")
        for b in info["breakdown"][:15]:  # type: ignore
            table.add_row(
                b["name"], "dir" if b["is_dir"] else "file", format_bytes(b["size"]), b["path"]
            )  # type: ignore
        console.print(table)

    if info["largest_files"]:
        ltable = create_table(title="Largest Files")
        ltable.add_column("Size", style="yellow", justify="right")
        ltable.add_column("Path", style="white")
        for f in info["largest_files"][:10]:  # type: ignore
            ltable.add_row(format_bytes(f["size"]), f["path"])  # type: ignore
        console.print(ltable)


@app.command("empty")
def empty_cmd(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Directory to scan"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Find empty directories."""
    root = _directory(path, json)

    results = find_empty_dirs(root, exclude_dirs=_exclude_dirs(ctx))
    if json:
        print_json(results)
        return

    if not results:
        console.print(f"[green]No empty directories found in {root}[/green]")
        return

    table = create_table(title=f"Empty Directories in {root} ({len(results)})")
    table.add_column("Path", style="white")
    for r in results[:50]:
        table.add_row(r)
    console.print(table)
    if len(results) > 50:
        console.print(f"[dim]... and {len(results) - 50} more[/dim]")
    console.print("[dim]Read-only scan — no directories were modified.[/dim]")


@app.command("duplicates")
def duplicates_cmd(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Directory to scan"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
    min_size: int = typer.Option(1, "--min-size", help="Minimum file size in bytes", min=0),
) -> None:
    """Find duplicate files by content hash."""
    root = _directory(path, json)

    results = find_duplicates(root, exclude_dirs=_exclude_dirs(ctx), min_size=min_size)
    if json:
        print_json(results)
        return
    console.print(f"[dim]Scanning for duplicates in {root} (hashing)...[/dim]")

    if not results:
        console.print(f"[green]No duplicates found in {root}[/green]")
        return

    for dup in results:
        console.print(
            f"\n[bold yellow]Duplicate group — {format_bytes(dup['size'])} × {dup['count']} files — hash {dup['hash'][:12]}...[/bold yellow]"
        )
        for f in dup["files"]:  # type: ignore
            console.print(f"  • {f}")
    console.print("\n[dim]No files were deleted. Review manually before removing duplicates.[/dim]")
