"""Git toolkit."""

from pathlib import Path

import typer

from forgekit.output import cli_error, create_table, get_console, print_json
from forgekit.services.git_service import get_branches, get_git_status, inspect_path, is_git_repo
from forgekit.utils import format_bytes

app = typer.Typer(help="Git repository toolkit.", no_args_is_help=False)
console = get_console()


@app.callback(invoke_without_command=True)
def git_main(
    ctx: typer.Context,
    path: str = typer.Option(".", "--path", "-p", help="Path to git repository"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    if ctx.invoked_subcommand is None:
        _show_status(Path(path), json)


def _show_status(repo_path: Path, as_json: bool) -> None:
    status = get_git_status(repo_path)
    if as_json:
        print_json(status.to_dict())
        if not status.is_repo or status.error:
            raise typer.Exit(1)
        return

    if not status.is_repo:
        console.print(f"[yellow]{status.error}: {repo_path.resolve()}[/yellow]")
        console.print("[dim]Run inside a git repository or specify --path[/dim]")
        raise typer.Exit(1)

    if status.error:
        console.print(f"[red]Git error: {status.error}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold cyan]Repository:[/bold cyan] {repo_path.resolve()}")
    console.print(
        f"[bold]Branch:[/bold] {status.branch or '—'}  [dim]•[/dim]  [bold]Commit:[/bold] {status.commit_short or '—'} {status.commit_message or ''}"
    )
    if status.ahead is not None or status.behind is not None:
        console.print(f"[dim]Ahead: {status.ahead}  Behind: {status.behind}[/dim]")

    # Status counts
    table = create_table(title="Working Tree Status")
    table.add_column("Category", style="cyan")
    table.add_column("Count", style="white", justify="right")
    table.add_column("Files", style="dim")
    table.add_row(
        "Staged",
        str(len(status.staged)),
        ", ".join(status.staged[:5]) + (" ..." if len(status.staged) > 5 else "")
        if status.staged
        else "—",
    )
    table.add_row(
        "Unstaged",
        str(len(status.unstaged)),
        ", ".join(status.unstaged[:5]) + (" ..." if len(status.unstaged) > 5 else "")
        if status.unstaged
        else "—",
    )
    table.add_row(
        "Untracked",
        str(len(status.untracked)),
        ", ".join(status.untracked[:5]) + (" ..." if len(status.untracked) > 5 else "")
        if status.untracked
        else "—",
    )
    console.print(table)

    if status.remotes:
        rtable = create_table(title="Remotes")
        rtable.add_column("Name", style="cyan")
        rtable.add_column("URL", style="white")
        for r in status.remotes:
            rtable.add_row(r["name"], r["url"])
        console.print(rtable)

    if status.recent_commits:
        ctable = create_table(title="Recent Commits")
        ctable.add_column("Hash", style="yellow")
        ctable.add_column("Message", style="white")
        ctable.add_column("Author", style="dim")
        ctable.add_column("When", style="dim")
        for c in status.recent_commits:
            ctable.add_row(c["hash"], c["message"][:50], c["author"], c["date"])
        console.print(ctable)

    if status.large_files:
        ltable = create_table(title="Large Tracked Files (>1 MB)")
        ltable.add_column("File", style="cyan")
        ltable.add_column("Size", style="white", justify="right")
        for f in status.large_files:
            ltable.add_row(f["path"], format_bytes(f["size"]))  # type: ignore
        console.print(ltable)

    if status.repo_size_bytes:
        console.print(f"[dim]Repository size: {format_bytes(status.repo_size_bytes)}[/dim]")


@app.command("status")
def status_cmd(
    path: str = typer.Option(".", "--path", "-p", help="Repository path"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show git status."""
    _show_status(Path(path), json)


@app.command("history")
def history_cmd(
    path: str = typer.Option(".", "--path", "-p", help="Repository path"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of commits", min=1, max=50),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Show commit history."""
    from forgekit.utils import run_command

    p = Path(path).resolve()
    if not is_git_repo(p):
        cli_error(f"Not a git repository or git unavailable: {p}", json)

    result = run_command(
        [
            "git",
            "log",
            f"-{limit}",
            "--pretty=format:%H%x00%h%x00%s%x00%an%x00%ar%x00%ad",
            "--date=short",
        ],
        cwd=p,
    )
    if result.returncode != 0:
        cli_error(f"Failed to get history: {result.stderr.strip()}", json)

    commits = []
    for line in result.stdout.splitlines():
        parts = line.split("\0", 5)
        if len(parts) == 6:
            commits.append(
                {
                    "hash": parts[0],
                    "short": parts[1],
                    "message": parts[2],
                    "author": parts[3],
                    "relative": parts[4],
                    "date": parts[5],
                }
            )

    if json:
        print_json(commits)
        return

    table = create_table(title=f"Commit History ({p})")
    table.add_column("Hash", style="yellow")
    table.add_column("Message", style="white")
    table.add_column("Author", style="cyan")
    table.add_column("Date", style="dim")
    for c in commits:
        table.add_row(c["short"], c["message"][:60], c["author"], c["date"])
    console.print(table)


@app.command("branches")
def branches_cmd(
    path: str = typer.Option(".", "--path", "-p", help="Repository path"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List branches."""
    p = Path(path).resolve()
    if not is_git_repo(p):
        cli_error(f"Not a git repository or git unavailable: {p}", json)

    try:
        data = get_branches(p)
    except (OSError, RuntimeError) as exc:
        cli_error(str(exc), json)
    if json:
        print_json(data)
        return

    console.print(f"[bold]Current branch:[/bold] {data['current'] or '—'}")
    if data["local"]:
        ltable = create_table(title="Local Branches")
        ltable.add_column("Branch", style="cyan")
        for b in data["local"]:
            style = "bold green" if "(current)" in b else "white"
            ltable.add_row(f"[{style}]{b}[/{style}]")
        console.print(ltable)
    if data["remote"]:
        rtable = create_table(title="Remote Branches")
        rtable.add_column("Branch", style="white")
        for b in data["remote"]:
            rtable.add_row(b)
        console.print(rtable)


@app.command("inspect")
def inspect_cmd(
    target: str = typer.Argument(..., help="File path to inspect"),
    path: str = typer.Option(".", "--path", "-p", help="Repository path"),
    json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Inspect a file's git history."""
    p = Path(target)
    repo = Path(path).resolve()
    info = inspect_path(p if p.is_absolute() else repo / p)
    if not info["exists"]:
        cli_error(f"Path not found: {target}", json)
    if json:
        print_json(info)
        return

    table = create_table(title=f"Inspect: {target}")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="white")
    for k, v in info.items():
        if isinstance(v, list):
            v = "\n".join(str(x) for x in v[:10])
        table.add_row(k, str(v)[:120])
    console.print(table)
