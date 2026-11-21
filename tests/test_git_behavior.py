"""Git subprocess, pathname, history and credential regressions."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.git_service import get_git_status, inspect_path
from forgekit.utils import redact_url, run_command

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is optional")


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def test_git_handles_renames_untracked_names_nested_paths_and_secrets(tmp_path):
    git(tmp_path, "init")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "Test User")
    (tmp_path / "nested").mkdir()
    old = tmp_path / "nested/old file.txt"
    old.write_text("hello")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-m", "initial | pipe")
    git(tmp_path, "mv", "nested/old file.txt", "nested/new file.txt")
    (tmp_path / "nested/untracked space.txt").write_text("x")
    git(
        tmp_path,
        "remote",
        "add",
        "origin",
        "https://token:supersecret@example.invalid/repo?access_token=private",
    )
    status = get_git_status(tmp_path)
    assert "nested/new file.txt" in status.staged
    assert "nested/untracked space.txt" in status.untracked
    assert "supersecret" not in json.dumps(status.to_dict())
    assert "private" not in json.dumps(status.to_dict())
    assert status.remotes[0]["url"] == "https://***@example.invalid/repo?***"
    # Inspect a tracked file from a nested directory before the staged rename is committed.
    git(tmp_path, "commit", "-m", "rename | message")
    info = inspect_path(tmp_path / "nested/new file.txt")
    assert any("rename | message" in line for line in info["git_history"])
    history = CliRunner().invoke(app, ["git", "history", "--path", str(tmp_path), "--json"])
    assert history.exit_code == 0
    assert json.loads(history.output)[0]["message"] == "rename | message"


def test_redact_url_masks_userinfo_query_and_scp_user():
    assert redact_url("ssh://user:secret@host/repo?token=abc#fragment") == "ssh://***@host/repo?***"
    assert redact_url("private-user@host:repo.git") == "***@host:repo.git"
    assert redact_url("/next?token=abc") == "/next?***"
    assert redact_url("//user:secret@host/path") == "//***@host/path"
    assert redact_url("token@host:repo?key=private") == "***@host:repo?***"


def test_git_subprocess_disables_configured_fsmonitor(tmp_path):
    git(tmp_path, "init")
    marker = tmp_path / "marker"
    hook = tmp_path / "hook.sh"
    hook.write_text(f"#!/bin/sh\ntouch '{marker}'\n")
    hook.chmod(0o755)
    git(tmp_path, "config", "core.fsmonitor", str(hook))
    result = run_command(["git", "status", "--porcelain"], cwd=tmp_path)
    assert result.returncode == 0
    assert not marker.exists()


def test_missing_git_executable_is_distinguished_from_non_repo(tmp_path, monkeypatch):
    import forgekit.services.git_service as service

    monkeypatch.setattr(
        service, "run_command", lambda *a, **kw: (_ for _ in ()).throw(FileNotFoundError("git"))
    )
    monkeypatch.setattr(service.shutil, "which", lambda name: None)
    result = get_git_status(tmp_path)
    assert not result.is_repo
    assert result.error == "Git executable not found in PATH"
