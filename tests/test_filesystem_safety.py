"""Read-only filesystem scanning and scaffolding regression tests."""

import importlib.util
import json
import os
import sys
import tomllib

import pytest
from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.filesystem_service import (
    directory_size,
    find_duplicates,
    find_empty_dirs,
    find_large_files,
    search_files,
)


def test_breakdown_is_single_consistent_accounting_with_exclusions(tmp_path):
    (tmp_path / "one").mkdir()
    (tmp_path / "one/a").write_bytes(b"1234")
    (tmp_path / "one/deep").mkdir()
    (tmp_path / "one/deep/b").write_bytes(b"123456")
    (tmp_path / "ignore").mkdir()
    (tmp_path / "ignore/c").write_bytes(b"123456789")
    (tmp_path / "root").write_bytes(b"12")
    result = directory_size(tmp_path, {"ignore"})
    assert result["total_size"] == 12
    assert result["file_count"] == 3
    sizes = {entry["name"]: entry["size"] for entry in result["breakdown"]}
    assert sizes == {"one": 10, "root": 2}
    assert sum(sizes.values()) == result["total_size"]


def test_duplicates_are_full_hash_not_just_size(tmp_path):
    (tmp_path / "one").write_bytes(b"abcd")
    (tmp_path / "two").write_bytes(b"abcd")
    (tmp_path / "three").write_bytes(b"abce")
    groups = find_duplicates(tmp_path)
    assert len(groups) == 1
    assert set(groups[0]["files"]) == {str(tmp_path / "one"), str(tmp_path / "two")}
    assert (tmp_path / "three").read_bytes() == b"abce"


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_symlinks_not_counted_and_follow_mode_avoids_loops(tmp_path):
    (tmp_path / "file").write_bytes(b"123")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub/loop").symlink_to(tmp_path, target_is_directory=True)
    (tmp_path / "linked-file").symlink_to(tmp_path / "file")
    assert directory_size(tmp_path)["total_size"] == 3
    assert [p["name"] for p in find_large_files(tmp_path, 1)] == ["file"]
    followed = find_large_files(tmp_path, 1, follow_symlinks=True)
    assert {p["name"] for p in followed} == {"file", "linked-file"}
    assert len(followed) == 2


def test_empty_means_physically_empty_even_with_exclusions(tmp_path):
    (tmp_path / "empty").mkdir()
    (tmp_path / "not-empty").mkdir()
    (tmp_path / "not-empty/ignored").mkdir()
    result = find_empty_dirs(tmp_path, {"ignored"})
    assert str(tmp_path / "empty") in result
    assert str(tmp_path / "not-empty") not in result


def test_search_extension_supports_common_wildcard_spelling(tmp_path):
    (tmp_path / "error.log").write_text("x")
    (tmp_path / "ignore.txt").write_text("x")
    assert [v["name"] for v in search_files(tmp_path, "*.log", by_extension=True)] == ["error.log"]


def test_scanning_non_directory_and_invalid_limits_fail_cleanly(tmp_path):
    file = tmp_path / "file"
    file.write_text("x")
    runner = CliRunner()
    result = runner.invoke(app, ["files", "size", str(file), "--json"])
    assert result.exit_code == 1
    assert "error" in json.loads(result.output)
    assert (
        runner.invoke(app, ["files", "search", str(tmp_path), "x", "--limit", "0"]).exit_code != 0
    )


@pytest.mark.parametrize("name", [".", "..", "bad/name", "two words", "9invalid", "class"])
def test_python_workspace_rejects_unsafe_or_invalid_names(tmp_path, name):
    result = CliRunner().invoke(app, ["workspace", "create", name, "--path", str(tmp_path)])
    assert result.exit_code != 0
    assert list(tmp_path.iterdir()) == []


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_workspace_force_refuses_existing_symlink_without_touching_target(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    target = tmp_path / "sensitive"
    target.write_text("private")
    (project / "README.md").symlink_to(target)
    result = CliRunner().invoke(
        app,
        [
            "workspace",
            "create",
            "demo",
            "-t",
            "generic",
            "--path",
            str(tmp_path),
            "--force",
            "--json",
        ],
    )
    assert result.exit_code == 1
    assert "symbolic link" in json.loads(result.output)["error"]
    assert target.read_text() == "private"
    assert not (project / ".gitignore").exists()


def test_workspace_templates_generate_valid_projects(tmp_path, monkeypatch):
    runner = CliRunner()
    py = runner.invoke(app, ["workspace", "create", "my-app", "--path", str(tmp_path), "--json"])
    assert py.exit_code == 0, py.output
    project = tmp_path / "my-app"
    assert tomllib.loads((project / "pyproject.toml").read_text())["project"]["name"] == "my-app"
    monkeypatch.syspath_prepend(str(project / "src"))
    spec = importlib.util.find_spec("my_app")
    assert spec is not None
    import my_app

    assert my_app.greeting() == "Hello from my-app"
    sys.modules.pop("my_app", None)
    node = runner.invoke(
        app, ["workspace", "create", "node-project", "--template", "node", "--path", str(tmp_path)]
    )
    assert node.exit_code == 0
    package = json.loads((tmp_path / "node-project/package.json").read_text())
    assert package["scripts"]["test"] == "node --test"
    assert (tmp_path / "node-project/test/index.test.js").is_file()


def test_workspace_preflight_rejects_blocked_parent_before_overwriting(tmp_path):
    project = tmp_path / "existing"
    project.mkdir()
    (project / "README.md").write_text("keep")
    (project / "src").write_text("not a directory")
    result = CliRunner().invoke(
        app, ["workspace", "create", "existing", "--path", str(tmp_path), "--force", "--json"]
    )
    assert result.exit_code == 1
    assert "directory" in json.loads(result.output)["error"]
    assert (project / "README.md").read_text() == "keep"
    assert (project / "src").read_text() == "not a directory"


def test_permission_error_is_logged_and_other_files_are_still_scanned(
    tmp_path, monkeypatch, caplog
):
    from pathlib import Path

    denied = tmp_path / "denied"
    denied.write_text("private")
    allowed = tmp_path / "allowed"
    allowed.write_text("hello")
    original = Path.lstat

    def fake_lstat(path):
        if path == denied:
            raise PermissionError("simulated denial")
        return original(path)

    monkeypatch.setattr(Path, "lstat", fake_lstat)
    result = find_large_files(tmp_path, threshold_bytes=1)
    assert [entry["name"] for entry in result] == ["allowed"]
    assert "simulated denial" in caplog.text


def test_workspace_parent_swap_does_not_write_outside_selected_directory(tmp_path, monkeypatch):
    import forgekit.commands.workspace as workspace

    parent = tmp_path / "parent"
    parent.mkdir()
    project = parent / "project"
    project.mkdir()
    (project / "README.md").write_text("original")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "project").mkdir()
    (outside / "project" / "README.md").write_text("outside sentinel")
    original = workspace._open_existing_directory

    def swap(path):
        parent.rename(tmp_path / "old-parent")
        parent.symlink_to(outside, target_is_directory=True)
        return original(path)

    monkeypatch.setattr(workspace, "_open_existing_directory", swap)
    result = CliRunner().invoke(
        app, ["workspace", "create", "project", "--path", str(parent), "--force", "--json"]
    )
    assert result.exit_code == 1
    assert "error" in json.loads(result.output)
    assert (outside / "project" / "README.md").read_text() == "outside sentinel"
    assert (tmp_path / "old-parent/project/README.md").read_text() == "original"


def test_workspace_interruption_reports_partial_files(tmp_path, monkeypatch):
    import forgekit.commands.workspace as workspace

    original = workspace._write_workspace_file
    calls = 0

    def interrupt(root_fd, relative, text, force):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated interruption")
        original(root_fd, relative, text, force)

    monkeypatch.setattr(workspace, "_write_workspace_file", interrupt)
    result = CliRunner().invoke(
        app, ["workspace", "create", "project", "--path", str(tmp_path), "--json"]
    )
    assert result.exit_code == 1
    assert "may remain" in json.loads(result.output)["error"]
    assert (tmp_path / "project/README.md").read_text().startswith("# project")
    assert not (tmp_path / "project/.gitignore").exists()
    assert not list((tmp_path / "project").glob(".forgekit-*.tmp"))


def test_git_init_stays_in_pinned_workspace_during_path_swap(tmp_path, monkeypatch):
    import shutil

    import forgekit.commands.workspace as workspace

    if not shutil.which("git"):
        pytest.skip("git is unavailable")
    parent = tmp_path / "parent"
    parent.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    original = workspace.run_command

    def swap_git(*args, **kwargs):
        (parent / "project").rename(parent / "moved-project")
        (parent / "project").symlink_to(outside, target_is_directory=True)
        return original(*args, **kwargs)

    monkeypatch.setattr(workspace, "run_command", swap_git)
    result = CliRunner().invoke(
        app,
        ["workspace", "create", "project", "--path", str(parent), "--git", "--json"],
    )
    assert result.exit_code == 0, (result.output, result.exception)
    assert (parent / "moved-project/.git").is_dir()
    assert not (outside / ".git").exists()


def test_workspace_git_failure_reports_created_files_without_hiding_error(tmp_path, monkeypatch):
    import forgekit.commands.workspace as workspace

    def missing_git(*args, **kwargs):
        raise FileNotFoundError("simulated missing Git")

    monkeypatch.setattr(workspace, "run_command", missing_git)
    result = CliRunner().invoke(
        app, ["workspace", "create", "project", "--path", str(tmp_path), "--git", "--json"]
    )
    assert result.exit_code == 1
    message = json.loads(result.output)["error"]
    assert "Git initialization failed" in message and "may remain" in message
    assert (tmp_path / "project/README.md").is_file()
    assert not (tmp_path / "project/.git").exists()


def test_workspace_symlink_loop_reports_json_error(tmp_path):
    loop = tmp_path / "loop"
    loop.symlink_to(loop, target_is_directory=True)
    result = CliRunner().invoke(
        app, ["workspace", "create", "project", "--path", str(loop), "--json"]
    )
    assert result.exit_code == 1
    assert "resolve" in json.loads(result.output)["error"].lower()
    assert not (tmp_path / "project").exists()
