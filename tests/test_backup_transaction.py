"""Restore transaction tests: a failed restore must not leave a partial tree."""

import io
import json
import os
import tarfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

import forgekit.services.backup_service as backup
from forgekit.cli import app
from forgekit.services.backup_service import RestoreError, create_backup, restore_archive

runner = CliRunner()


def make_tar(path: Path, files: dict[str, bytes]) -> None:
    with tarfile.open(path, "w") as archive:
        for name, data in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(data)
            archive.addfile(member, io.BytesIO(data))


def fail_nth(monkeypatch, n: int, error: BaseException | None = None) -> dict[str, int]:
    """Let the nth extracted file land, then raise to simulate a mid-restore failure."""
    original = backup._restore_file
    state = {"calls": 0}

    def flaky(*args, **kwargs):
        original(*args, **kwargs)
        state["calls"] += 1
        if state["calls"] == n:
            raise error or OSError("simulated disk exhaustion")

    monkeypatch.setattr(backup, "_restore_file", flaky)
    return state


def test_failed_restore_removes_files_and_directories_it_created(tmp_path, monkeypatch):
    archive = tmp_path / "two.tar"
    make_tar(archive, {"pkg/one.txt": b"one", "pkg/nested/two.txt": b"two"})
    destination = tmp_path / "restore"
    fail_nth(monkeypatch, 2)

    with pytest.raises(RestoreError) as info:
        restore_archive(archive, destination, overwrite=True)

    assert info.value.rolled_back is True
    assert info.value.rollback_errors == []
    assert "rolled back" in str(info.value)
    assert not destination.exists()


def test_failed_restore_restores_overwritten_originals(tmp_path, monkeypatch):
    archive = tmp_path / "payload.tar"
    make_tar(archive, {"pkg/keep.txt": b"new contents", "pkg/b.txt": b"second"})
    destination = tmp_path / "restore"
    (destination / "pkg").mkdir(parents=True)
    original = destination / "pkg" / "keep.txt"
    original.write_text("original contents")
    destination_entries_before = sorted(p.name for p in destination.iterdir())

    fail_nth(monkeypatch, 2)
    with pytest.raises(RestoreError) as info:
        restore_archive(archive, destination, overwrite=True)

    assert info.value.rolled_back is True
    assert original.read_text() == "original contents"
    assert sorted(p.name for p in destination.iterdir()) == destination_entries_before
    assert not any(p.name.startswith(".forgekit-restore-") for p in destination.iterdir())


def test_successful_restore_replaces_original_and_leaves_no_journal(tmp_path):
    archive = tmp_path / "payload.tar"
    make_tar(archive, {"pkg/keep.txt": b"new contents"})
    destination = tmp_path / "restore"
    destination.mkdir()
    (destination / "pkg").mkdir()
    (destination / "pkg" / "keep.txt").write_text("old contents")

    result = restore_archive(archive, destination, overwrite=True)

    assert result["status"] == "restored"
    assert result["overwritten"] == 1
    assert (destination / "pkg" / "keep.txt").read_bytes() == b"new contents"
    assert not any(p.name.startswith(".forgekit-restore-") for p in destination.iterdir())


def test_conflict_without_force_writes_nothing(tmp_path):
    archive = tmp_path / "payload.tar"
    make_tar(archive, {"pkg/a.txt": b"new", "pkg/b.txt": b"new"})
    destination = tmp_path / "restore"
    destination.mkdir()
    (destination / "pkg").mkdir()
    (destination / "pkg" / "b.txt").write_text("old")

    result = restore_archive(archive, destination)

    assert result["status"] == "needs_confirmation"
    assert not (destination / "pkg" / "a.txt").exists()
    assert (destination / "pkg" / "b.txt").read_text() == "old"


def test_rollback_reports_incomplete_state_honestly(tmp_path, monkeypatch):
    archive = tmp_path / "payload.tar"
    make_tar(archive, {"pkg/a.txt": b"a", "pkg/b.txt": b"b"})
    destination = tmp_path / "restore"
    fail_nth(monkeypatch, 2)
    open_existing = backup._open_existing_directory

    def broken_open(root_fd, parts):
        raise OSError("simulated rollback failure")

    monkeypatch.setattr(backup, "_open_existing_directory", broken_open)
    with pytest.raises(RestoreError) as info:
        restore_archive(archive, destination, overwrite=True)

    assert info.value.rolled_back is False
    assert info.value.rollback_errors
    assert "rollback was incomplete" in str(info.value)
    monkeypatch.setattr(backup, "_open_existing_directory", open_existing)


def test_interrupt_during_restore_rolls_back_and_propagates(tmp_path, monkeypatch):
    archive = tmp_path / "payload.tar"
    make_tar(archive, {"pkg/a.txt": b"a", "pkg/b.txt": b"b"})
    destination = tmp_path / "restore"
    destination.mkdir()
    (destination / "pkg").mkdir()
    (destination / "pkg" / "a.txt").write_text("old")
    fail_nth(monkeypatch, 2, KeyboardInterrupt())

    with pytest.raises(KeyboardInterrupt):
        restore_archive(archive, destination, overwrite=True)

    assert (destination / "pkg" / "a.txt").read_text() == "old"
    assert not (destination / "pkg" / "b.txt").exists()


def test_cli_json_reports_rolled_back_restore(tmp_path, monkeypatch):
    archive = tmp_path / "payload.tar"
    make_tar(archive, {"pkg/a.txt": b"a", "pkg/b.txt": b"b"})
    fail_nth(monkeypatch, 2)

    result = runner.invoke(
        app, ["backup", "restore", str(archive), str(tmp_path / "out"), "--force", "--json"]
    )

    assert result.exit_code == 1, result.output
    payload = json.loads(result.stdout)
    assert payload["rolled_back"] is True
    assert payload["rollback_errors"] == []
    assert "rolled back" in payload["error"]


def test_cli_text_reports_rollback(tmp_path, monkeypatch):
    archive = tmp_path / "payload.tar"
    make_tar(archive, {"pkg/a.txt": b"a", "pkg/b.txt": b"b"})
    fail_nth(monkeypatch, 2)

    result = runner.invoke(
        app, ["backup", "restore", str(archive), str(tmp_path / "out"), "--force"]
    )

    assert result.exit_code == 1
    assert "rolled back" in result.output
    assert not (tmp_path / "out").exists()


def test_restore_preserves_original_mode_and_content_across_rollback(tmp_path, monkeypatch):
    archive = tmp_path / "payload.tar"
    make_tar(archive, {"f.txt": b"replacement", "g.txt": b"g"})
    destination = tmp_path / "restore"
    destination.mkdir()
    target = destination / "f.txt"
    target.write_text("original")
    target.chmod(0o640)

    fail_nth(monkeypatch, 2)
    with pytest.raises(RestoreError):
        restore_archive(archive, destination, overwrite=True)

    assert target.read_text() == "original"
    assert oct(target.stat().st_mode & 0o777) == oct(0o640)


def test_backup_roundtrip_still_restores_nested_trees(tmp_path):
    source = tmp_path / "source"
    (source / "a" / "b").mkdir(parents=True)
    (source / "a" / "b" / "c.txt").write_text("deep")
    (source / "top.txt").write_text("top")
    archive = tmp_path / "tree.tar.gz"
    create_backup(source, archive)

    result = restore_archive(archive, tmp_path / "out")

    assert result["status"] == "restored"
    assert (tmp_path / "out" / "source" / "a" / "b" / "c.txt").read_text() == "deep"
    assert (tmp_path / "out" / "source" / "top.txt").read_text() == "top"
    assert not any(
        p.name.startswith(".forgekit-restore-") for p in (tmp_path / "out" / "source").iterdir()
    )
    assert not os.path.exists(tmp_path / "out" / source.name / ".forgekit-restore-")
