"""Remaining CLI paths: backup text output, dashboard modes, doctor branches, git errors."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.backup_service import create_backup

runner = CliRunner()


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "file.txt").write_text("contents")
    return source


# --- backup ---------------------------------------------------------------


def test_backup_create_list_verify_text(tmp_path):
    source = _source(tmp_path)
    archive = tmp_path / "backup.tar.gz"
    created = runner.invoke(app, ["backup", "create", str(source), str(archive)])
    assert created.exit_code == 0
    assert "Backup created" in created.output
    assert "SHA-256" in created.output

    listed = runner.invoke(app, ["backup", "list", str(archive)])
    assert listed.exit_code == 0
    assert "file.txt" in listed.output

    verified = runner.invoke(app, ["backup", "verify", str(archive)])
    assert verified.exit_code == 0
    assert "Archive readable" in verified.output

    dry = runner.invoke(
        app, ["backup", "create", str(source), str(tmp_path / "dry.tar.gz"), "--dry-run"]
    )
    assert dry.exit_code == 0
    assert "Dry run" in dry.output
    assert "Estimated size" in dry.output


def test_backup_verify_reports_invalid_text(tmp_path):
    broken = tmp_path / "broken.tar.gz"
    broken.write_bytes(b"not an archive")
    result = runner.invoke(app, ["backup", "verify", str(broken)])
    assert result.exit_code == 1
    assert "invalid or unsafe" in result.output

    listed = runner.invoke(app, ["backup", "list", str(broken)])
    assert listed.exit_code == 1
    assert "Failed to list archive" in listed.output


def test_backup_create_failure_text(tmp_path):
    result = runner.invoke(
        app, ["backup", "create", str(tmp_path / "missing"), str(tmp_path / "b.tar.gz")]
    )
    assert result.exit_code == 1
    assert "Backup failed" in result.output


def test_backup_restore_text_success_dry_run_and_conflict(tmp_path):
    source = _source(tmp_path)
    archive = tmp_path / "backup.tar.gz"
    create_backup(source, archive)
    destination = tmp_path / "restore"

    dry = runner.invoke(app, ["backup", "restore", str(archive), str(destination), "--dry-run"])
    assert dry.exit_code == 0
    assert "Dry run" in dry.output
    assert not destination.exists()

    restored = runner.invoke(app, ["backup", "restore", str(archive), str(destination)])
    assert restored.exit_code == 0
    assert "Restored" in restored.output

    force = runner.invoke(app, ["backup", "restore", str(archive), str(destination), "--force"])
    assert force.exit_code == 0
    assert "Replaced" in force.output

    (destination / "source" / "file.txt").write_text("changed")
    conflict = runner.invoke(app, ["backup", "restore", str(archive), str(destination)])
    assert conflict.exit_code == 1
    assert "would be overwritten" in conflict.output
    assert "restore/source" in conflict.output.replace("\n", "")


def test_backup_restore_missing_archive_text(tmp_path):
    result = runner.invoke(
        app, ["backup", "restore", str(tmp_path / "none.tar"), str(tmp_path / "out")]
    )
    assert result.exit_code == 1
    assert "Restore failed" in result.output


# --- dashboard ------------------------------------------------------------


def test_dashboard_json_snapshot():
    result = runner.invoke(app, ["dashboard", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["hostname"]
    assert "cpu" in payload


def test_dashboard_rejects_out_of_range_refresh(tmp_path):
    result = runner.invoke(app, ["dashboard", "--refresh", "0.1"])
    assert result.exit_code == 1
    assert "between 0.5 and 60" in result.output


def test_dashboard_uses_configured_interval_and_ignores_bad_values(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text("[dashboard]\nrefresh_interval = 2.5\nshow_processes = false\n")
    result = runner.invoke(app, ["--config", str(config), "dashboard"])
    assert result.exit_code == 0
    assert "refresh: 2.5s" in result.output

    bad = tmp_path / "bad.toml"
    bad.write_text("[dashboard]\nrefresh_interval = 900\n")
    rejected = runner.invoke(app, ["--config", str(bad), "dashboard"])
    assert rejected.exit_code == 1
    assert "between 0.5 and 60" in rejected.output


def test_dashboard_interactive_exits_cleanly_on_interrupt(monkeypatch, tmp_path):
    import forgekit.commands.dashboard as dashboard

    monkeypatch.setattr(type(dashboard.console), "is_terminal", property(lambda self: True))

    def interrupt(seconds):
        raise KeyboardInterrupt

    monkeypatch.setattr(dashboard.time, "sleep", interrupt)
    result = runner.invoke(app, ["dashboard"])
    assert result.exit_code == 0
    assert "Dashboard exited" in result.output


# --- doctor ---------------------------------------------------------------


def test_doctor_invalid_config_fails_with_json(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("[general]\nlog_level = 'LOUD'\n")
    result = runner.invoke(app, ["--config", str(bad), "doctor", "--json"])
    assert result.exit_code == 1
    checks = json.loads(result.stdout)
    config_check = next(check for check in checks if check["name"] == "Configuration")
    assert config_check["status"] == "fail"
    assert "log_level" in config_check["message"]


def test_doctor_warns_when_root(monkeypatch):
    import forgekit.commands.doctor as doctor

    monkeypatch.setattr(doctor, "is_root", lambda: True)
    result = runner.invoke(app, ["doctor", "--json"])
    checks = json.loads(result.stdout)
    permissions_check = next(check for check in checks if check["name"] == "Permissions")
    assert permissions_check["status"] == "warn"


def test_doctor_reports_source_install(monkeypatch):
    import importlib.metadata as metadata

    import forgekit.commands.doctor as doctor

    def missing(name):
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(doctor.importlib_metadata, "version", missing)
    result = runner.invoke(app, ["doctor", "--json"])
    checks = json.loads(result.stdout)
    install = next(check for check in checks if check["name"] == "Installation")
    assert install["status"] in ("warn", "pass")
    assert "source" in install["message"] or "forgekit" in install["message"]


# --- git ------------------------------------------------------------------


def test_git_history_failure_text(tmp_path, monkeypatch):
    import forgekit.commands.git as git_command

    monkeypatch.setattr(git_command, "is_git_repo", lambda path: True)

    def failing(*args, **kwargs):
        return subprocess.CompletedProcess(args, 128, "", "fatal: bad revision")

    monkeypatch.setattr("forgekit.utils.run_command", failing)
    result = runner.invoke(app, ["git", "history", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "Failed to get history" in result.output


def test_git_branches_failure_text(tmp_path, monkeypatch):
    import forgekit.commands.git as git_command

    monkeypatch.setattr(git_command, "is_git_repo", lambda path: True)
    monkeypatch.setattr(
        git_command, "get_branches", lambda path: (_ for _ in ()).throw(RuntimeError("no branches"))
    )
    result = runner.invoke(app, ["git", "branches", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "no branches" in result.output


def test_git_inspect_missing_text(tmp_path):
    result = runner.invoke(app, ["git", "inspect", "nope.txt", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "Path not found" in result.output


def test_git_status_error_text(tmp_path, monkeypatch):
    import forgekit.commands.git as git_command
    from forgekit.models.git_info import GitStatus

    def broken(path):
        return GitStatus(
            is_repo=True,
            branch="main",
            commit=None,
            commit_short=None,
            commit_message=None,
            staged=[],
            unstaged=[],
            untracked=[],
            error="git status failed",
        )

    monkeypatch.setattr(git_command, "get_git_status", broken)
    result = runner.invoke(app, ["git", "status", "--path", str(tmp_path)])
    assert result.exit_code == 1
    assert "Git error" in result.output


# --- entry point ----------------------------------------------------------


def test_python_module_entry_point_reports_version():
    result = subprocess.run(
        [sys.executable, "-m", "forgekit", "--version"], capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0
    assert "ForgeKit version" in result.stdout


# --- storage --------------------------------------------------------------


def test_history_reports_unusable_directory(tmp_path):
    from forgekit.storage import history

    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory")
    with pytest.raises((OSError, NotADirectoryError)):
        history.get_db(blocker / "history.db")


def test_verbose_logging_goes_to_stderr_and_keeps_json_clean():
    verbose = runner.invoke(app, ["--verbose", "--json", "system", "cpu"])
    assert verbose.exit_code == 0
    assert "DEBUG: forgekit" in verbose.stderr
    assert json.loads(verbose.stdout)["logical_cores"] >= 1

    quiet = runner.invoke(app, ["--json", "system", "cpu"])
    assert quiet.exit_code == 0
    assert quiet.stderr == ""
