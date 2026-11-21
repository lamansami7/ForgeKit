"""Git models."""

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class GitStatus:
    is_repo: bool
    branch: str | None
    commit: str | None
    commit_short: str | None
    commit_message: str | None
    staged: list[str]
    unstaged: list[str]
    untracked: list[str]
    ahead: int | None = None
    behind: int | None = None
    remotes: list[dict[str, str]] | None = None
    recent_commits: list[dict[str, str]] | None = None
    large_files: list[dict[str, Any]] | None = None
    repo_size_bytes: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GitRepoInfo:
    path: str
    is_repo: bool
    branch: str | None
    status: GitStatus | None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.status:
            d["status"] = self.status.to_dict()
        return d
