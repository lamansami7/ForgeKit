"""Backup tests."""

from pathlib import Path

from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.backup_service import (
    create_backup,
    list_archive,
    restore_archive,
    verify_archive,
)

runner = CliRunner()


def test_backup_create_and_verify_and_restore(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("hello")
    (src / "b.txt").write_text("world")
    sub = src / "sub"
    sub.mkdir()
    (sub / "c.txt").write_text("nested")

    dest = tmp_path / "backups"
    dest.mkdir()

    # Dry run
    dry = create_backup(src, dest, compression="gz", dry_run=True)
    assert dry["dry_run"] is True

    # Actual create
    result = create_backup(src, dest, compression="gz")
    assert "archive" in result
    archive = Path(result["archive"])
    assert archive.exists()

    # List
    members = list_archive(archive)
    assert len(members) > 0

    # Verify
    v = verify_archive(archive)
    assert v["valid"] is True

    # Restore dry-run
    restore_dest = tmp_path / "restore"
    r_dry = restore_archive(archive, restore_dest, dry_run=True)
    assert r_dry["status"] == "dry_run"

    # Restore actual
    r = restore_archive(archive, restore_dest, overwrite=False)
    assert r["status"] == "restored"
    assert (restore_dest / src.name / "a.txt").exists() or (restore_dest / "a.txt").exists()

    # Ensure source not deleted
    assert (src / "a.txt").exists()


def test_backup_overwrite_protection(tmp_path):
    src = tmp_path / "src2"
    src.mkdir()
    (src / "f.txt").write_text("x")
    dest = tmp_path / "out.tar.gz"
    create_backup(src, dest, compression="gz")
    # Try to overwrite same dest
    try:
        create_backup(src, dest, compression="gz")
        raise AssertionError("Should have raised FileExistsError")
    except FileExistsError:
        pass


def test_backup_cli_create(tmp_path):
    src = tmp_path / "mydata"
    src.mkdir()
    (src / "file.txt").write_text("content")
    dest = tmp_path / "backup.tar.gz"
    result = runner.invoke(app, ["backup", "create", str(src), str(dest)])
    assert result.exit_code == 0
    assert dest.exists()


def test_backup_cli_dry_run(tmp_path):
    src = tmp_path / "src3"
    src.mkdir()
    (src / "f.txt").write_text("x")
    result = runner.invoke(
        app, ["backup", "create", str(src), str(tmp_path / "dummy.tar.gz"), "--dry-run"]
    )
    assert result.exit_code == 0


def test_backup_cli_list(tmp_path):
    src = tmp_path / "src4"
    src.mkdir()
    (src / "a.txt").write_text("hi")
    dest = tmp_path / "arc.tar.gz"
    create_backup(src, dest)
    result = runner.invoke(app, ["backup", "list", str(dest)])
    assert result.exit_code == 0


def test_backup_cli_verify(tmp_path):
    src = tmp_path / "src5"
    src.mkdir()
    (src / "a.txt").write_text("hi")
    dest = tmp_path / "v.tar.gz"
    create_backup(src, dest)
    result = runner.invoke(app, ["backup", "verify", str(dest)])
    assert result.exit_code == 0


def test_backup_cli_restore_conflict(tmp_path):
    src = tmp_path / "src6"
    src.mkdir()
    (src / "a.txt").write_text("hi")
    dest = tmp_path / "r.tar.gz"
    create_backup(src, dest)
    out = tmp_path / "restore2"
    out.mkdir()
    (out / src.name).mkdir(parents=True, exist_ok=True)
    (out / src.name / "a.txt").write_text("existing")
    # Try restore without force — should fail with conflict
    result = runner.invoke(app, ["backup", "restore", str(dest), str(out)])
    assert result.exit_code != 0
    # With force should succeed
    result2 = runner.invoke(app, ["backup", "restore", str(dest), str(out), "--force"])
    assert result2.exit_code == 0


def test_backup_single_file(tmp_path):
    f = tmp_path / "single.txt"
    f.write_text("hello file backup")
    dest = tmp_path / "single.tar.gz"
    result = create_backup(f, dest)
    assert Path(result["archive"]).exists()
    v = verify_archive(Path(result["archive"]))
    assert v["valid"]


def test_backup_compression_variants(tmp_path):
    src = tmp_path / "csrc"
    src.mkdir()
    (src / "f.txt").write_text("data")
    for comp in ["gz", "none"]:
        dest = tmp_path / f"arc_{comp}.tar.gz" if comp != "none" else tmp_path / f"arc_{comp}.tar"
        create_backup(src, dest, compression=comp)
        assert dest.exists()
