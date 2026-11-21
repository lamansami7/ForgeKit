"""Git tests."""

import subprocess

from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.git_service import get_git_status, is_git_repo

runner = CliRunner()


def test_not_a_repo(tmp_path):
    # tmp_path is empty, not a repo
    assert is_git_repo(tmp_path) is False
    status = get_git_status(tmp_path)
    assert status.is_repo is False


def test_git_status_cli_outside_repo(tmp_path):
    result = runner.invoke(app, ["git", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "Not a git repository" in result.output


def test_git_json_outside_repo(tmp_path):
    result = runner.invoke(app, ["git", "--path", str(tmp_path), "--json"])
    assert result.exit_code == 1
    import json

    data = json.loads(result.output)
    assert data["is_repo"] is False


def test_git_repo_lifecycle(tmp_path):
    # Create a temp git repo
    repo = tmp_path / "testrepo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, capture_output=True)
    (repo / "README.md").write_text("# Test")
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, capture_output=True)

    assert is_git_repo(repo) is True
    status = get_git_status(repo)
    assert status.is_repo is True
    assert status.branch is not None
    assert status.commit is not None

    # CLI status
    result = runner.invoke(app, ["git", "status", "--path", str(repo)])
    assert result.exit_code == 0

    result = runner.invoke(app, ["git", "history", "--path", str(repo), "--limit", "5"])
    assert result.exit_code == 0
    assert "initial" in result.output or "Test" in result.output

    result = runner.invoke(app, ["git", "branches", "--path", str(repo)])
    assert result.exit_code == 0

    # Inspect
    result = runner.invoke(app, ["git", "inspect", "README.md", "--path", str(repo)])
    assert result.exit_code == 0


def test_branches_outside_repo(tmp_path):
    result = runner.invoke(app, ["git", "branches", "--path", str(tmp_path)])
    assert result.exit_code == 1
