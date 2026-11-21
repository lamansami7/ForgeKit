"""Git services."""

import re
from pathlib import Path

from forgekit.models.git_info import GitStatus
from forgekit.utils import redact_url, run_command


def is_git_repo(path: Path | str = ".") -> bool:
    try:
        result = run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=path, timeout=5)
        return result.returncode == 0 and result.stdout.strip() == "true"
    except Exception:
        return False


def find_repo_root(path: Path | str = ".") -> Path | None:
    try:
        result = run_command(["git", "rev-parse", "--show-toplevel"], cwd=path, timeout=5)
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return None


def get_git_status(path: Path | str = ".") -> GitStatus:
    p = Path(path).resolve()
    if not is_git_repo(p):
        return GitStatus(
            is_repo=False,
            branch=None,
            commit=None,
            commit_short=None,
            commit_message=None,
            staged=[],
            unstaged=[],
            untracked=[],
            error="Not a git repository",
        )

    branch: str | None = None
    commit: str | None = None
    commit_short: str | None = None
    commit_message: str | None = None
    staged: list[str] = []
    unstaged: list[str] = []
    untracked: list[str] = []
    ahead: int | None = None
    behind: int | None = None
    remotes: list[dict[str, str]] | None = None
    recent_commits: list[dict[str, str]] | None = None
    large_files: list[dict[str, object]] | None = None
    repo_size_bytes: int | None = None

    try:
        # Branch
        r = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=p)
        if r.returncode == 0:
            branch = r.stdout.strip()

        # Commit
        r = run_command(["git", "rev-parse", "HEAD"], cwd=p)
        if r.returncode == 0:
            commit = r.stdout.strip()
            commit_short = commit[:7]

        r = run_command(["git", "log", "-1", "--pretty=%s"], cwd=p)
        if r.returncode == 0:
            commit_message = r.stdout.strip()

        # Porcelain status
        r = run_command(["git", "status", "--porcelain=v1"], cwd=p)
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                if not line:
                    continue
                code = line[:2]
                filepath = line[3:]
                # Handle renames: "R  old -> new"
                if " -> " in filepath:
                    filepath = filepath.split(" -> ")[-1]
                if code[0] in ("M", "A", "D", "R", "C"):
                    staged.append(filepath)
                if code[1] in ("M", "D"):
                    unstaged.append(filepath)
                if code == "??":
                    untracked.append(filepath)
                    # untracked is not staged/unstaged, remove if added earlier
                    if filepath in staged:
                        staged.remove(filepath)

        # Ahead/behind
        try:
            r = run_command(["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"], cwd=p)
            if r.returncode == 0:
                parts = r.stdout.strip().split()
                if len(parts) == 2:
                    ahead = int(parts[0])
                    behind = int(parts[1])
        except Exception:
            pass

        # Remotes
        r = run_command(["git", "remote", "-v"], cwd=p)
        if r.returncode == 0 and r.stdout.strip():
            remotes = []
            seen = set()
            for line in r.stdout.splitlines():
                m = re.match(r"(\S+)\s+(\S+)\s+\((fetch|push)\)", line)
                if m:
                    name, url, _ = m.groups()
                    if name not in seen:
                        seen.add(name)
                        remotes.append({"name": name, "url": redact_url(url)})

        # Recent commits: last 5
        r = run_command(["git", "log", "--oneline", "-5", "--pretty=format:%H|%s|%an|%ar"], cwd=p)
        if r.returncode == 0 and r.stdout.strip():
            recent_commits = []
            for line in r.stdout.splitlines():
                parts = line.split("|", 3)
                if len(parts) == 4:
                    recent_commits.append(
                        {
                            "hash": parts[0][:7],
                            "message": parts[1],
                            "author": parts[2],
                            "date": parts[3],
                        }
                    )

        # Repo size
        try:
            obj_dir = p / ".git"
            if not obj_dir.exists():
                # worktree
                r2 = run_command(["git", "rev-parse", "--git-dir"], cwd=p)
                if r2.returncode == 0:
                    obj_dir = Path(r2.stdout.strip())
                    if not obj_dir.is_absolute():
                        obj_dir = p / obj_dir
            repo_size_bytes = sum(f.stat().st_size for f in obj_dir.rglob("*") if f.is_file())
        except Exception:
            pass

        # Large files: check git ls-files and size >1MB
        try:
            r = run_command(["git", "ls-files", "-z"], cwd=p)
            if r.returncode == 0:
                large = []
                for fname in r.stdout.split("\0"):
                    if not fname:
                        continue
                    fp = p / fname
                    try:
                        sz = fp.stat().st_size
                        if sz > 1 * 1024 * 1024:
                            large.append({"path": fname, "size": sz})
                    except Exception:
                        continue
                large.sort(key=lambda x: x["size"], reverse=True)  # type: ignore
                large_files = large[:10]
        except Exception:
            pass

    except Exception as e:
        return GitStatus(
            is_repo=True,
            branch=branch,
            commit=commit,
            commit_short=commit_short,
            commit_message=commit_message,
            staged=staged,
            unstaged=unstaged,
            untracked=untracked,
            error=str(e),
        )

    return GitStatus(
        is_repo=True,
        branch=branch,
        commit=commit,
        commit_short=commit_short,
        commit_message=commit_message,
        staged=staged,
        unstaged=unstaged,
        untracked=untracked,
        ahead=ahead,
        behind=behind,
        remotes=remotes,
        recent_commits=recent_commits,
        large_files=large_files,
        repo_size_bytes=repo_size_bytes,
    )


def get_branches(path: Path | str = ".") -> dict[str, list[str]]:
    p = Path(path).resolve()
    local: list[str] = []
    remote: list[str] = []
    current: str | None = None
    try:
        r = run_command(["git", "branch", "--format=%(refname:short) %(HEAD)"], cwd=p)
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                parts = line.strip().split()
                if not parts:
                    continue
                name = parts[0]
                is_current = len(parts) > 1 and parts[1] == "*"
                if is_current:
                    current = name
                local.append(name + (" (current)" if is_current else ""))

        r = run_command(["git", "branch", "-r", "--format=%(refname:short)"], cwd=p)
        if r.returncode == 0:
            for line in r.stdout.splitlines():
                name = line.strip()
                if name:
                    remote.append(name)
    except Exception:
        pass
    return {"local": local, "remote": remote, "current": current or ""}


def inspect_path(path: Path | str) -> dict[str, object]:
    p = Path(path).resolve()
    info: dict[str, object] = {"path": str(p), "exists": p.exists()}
    if not p.exists():
        return info
    info["is_file"] = p.is_file()
    info["is_dir"] = p.is_dir()
    try:
        st = p.stat()
        info["size"] = st.st_size
        info["mode"] = oct(st.st_mode & 0o777)
    except Exception:
        pass
    # git log for file if repo
    try:
        parent = p.parent if p.is_file() else p
        if is_git_repo(parent):
            rel = p.relative_to(find_repo_root(parent) or parent)
            r = run_command(["git", "log", "--oneline", "-5", "--", str(rel)], cwd=parent)
            if r.returncode == 0 and r.stdout.strip():
                info["git_history"] = r.stdout.strip().splitlines()
            r = run_command(
                ["git", "log", "--diff-filter=A", "--follow", "--format=%aI", "--", str(rel)],
                cwd=parent,
            )
            if r.returncode == 0 and r.stdout.strip():
                info["first_seen"] = r.stdout.strip().splitlines()[-1]
    except Exception:
        pass
    return info
