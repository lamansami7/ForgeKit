"""Regression tests for data loss and untrusted tar archives."""

import io
import json
import os
import tarfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.backup_service import create_backup, restore_archive, verify_archive


def make_tar(path: Path, entries: list[tuple[str, bytes | str, bytes]]) -> None:
    with tarfile.open(path, "w") as archive:
        for name, kind, data in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            if kind == tarfile.REGTYPE:
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data))
            else:
                member.linkname = data.decode()
                archive.addfile(member)


@pytest.mark.parametrize(
    "name",
    ["../outside", "../../out", "/absolute", "safe/../../outside", "C:/escape", "safe\\..\\escape"],
)
def test_rejects_unsafe_paths_without_writing(tmp_path, name):
    archive = tmp_path / "bad.tar"
    destination = tmp_path / "dest"
    sentinel = tmp_path / "outside"
    sentinel.write_text("untouched")
    make_tar(archive, [(name, tarfile.REGTYPE, b"attacker")])
    with pytest.raises(ValueError, match="Unsafe archive path"):
        restore_archive(archive, destination, overwrite=True)
    assert sentinel.read_text() == "untouched"
    assert not destination.exists()
    assert verify_archive(archive)["valid"] is False


@pytest.mark.parametrize(
    "kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE]
)
def test_rejects_archive_links_and_special_files(tmp_path, kind):
    archive = tmp_path / "bad.tar"
    make_tar(archive, [("link", kind, b"../../outside"), ("link/file", tarfile.REGTYPE, b"data")])
    with pytest.raises(ValueError, match="Unsupported archive member"):
        restore_archive(archive, tmp_path / "dest", overwrite=True)
    assert not (tmp_path / "dest").exists()


def test_prefix_sibling_traversal_is_rejected(tmp_path):
    archive = tmp_path / "bad.tar"
    make_tar(archive, [("../dest-sibling/stolen", tarfile.REGTYPE, b"bad")])
    with pytest.raises(ValueError):
        restore_archive(archive, tmp_path / "dest")
    assert not (tmp_path / "dest-sibling").exists()


def test_duplicate_and_conflicting_members_rejected(tmp_path):
    archive = tmp_path / "duplicates.tar"
    make_tar(archive, [("file", tarfile.REGTYPE, b"one"), ("file", tarfile.REGTYPE, b"two")])
    with pytest.raises(ValueError, match="Duplicate"):
        restore_archive(archive, tmp_path / "out")
    make_tar(archive, [("x/y", tarfile.REGTYPE, b"one"), ("x", tarfile.REGTYPE, b"two")])
    with pytest.raises(ValueError, match="parent directory"):
        restore_archive(archive, tmp_path / "out")


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_existing_symlink_and_broken_symlink_are_never_overwritten(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "file").write_text("backup")
    archive = tmp_path / "backup.tar.gz"
    create_backup(src, archive)
    out = tmp_path / "out"
    (out / "src").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.write_text("private")
    (out / "src" / "file").symlink_to(outside)
    with pytest.raises(ValueError, match="symbolic link"):
        restore_archive(archive, out, overwrite=True)
    assert outside.read_text() == "private"
    (out / "src" / "file").unlink()
    (out / "src" / "file").symlink_to(tmp_path / "absent")
    with pytest.raises(ValueError, match="symbolic link"):
        restore_archive(archive, out, overwrite=True)
    assert not (tmp_path / "absent").exists()


def test_restore_conflicts_are_reported_on_dry_run_and_require_force(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "a").write_text("new")
    archive = tmp_path / "backup.tar"
    create_backup(source, archive, compression="none")
    out = tmp_path / "out"
    (out / "source").mkdir(parents=True)
    (out / "source" / "a").write_text("old")
    preview = restore_archive(archive, out, dry_run=True)
    assert preview["conflict_count"] == 1
    assert restore_archive(archive, out)["status"] == "needs_confirmation"
    assert (out / "source" / "a").read_text() == "old"
    assert restore_archive(archive, out, overwrite=True)["status"] == "restored"
    assert (out / "source" / "a").read_text() == "new"
    assert (source / "a").read_text() == "new"


@pytest.mark.parametrize(
    "compression,suffix",
    [("none", ".tar"), ("gz", ".tar.gz"), ("bz2", ".tar.bz2"), ("xz", ".tar.xz")],
)
def test_roundtrip_all_compressions_and_trusted_checksum(tmp_path, compression, suffix):
    source = tmp_path / "source"
    (source / "deep").mkdir(parents=True)
    (source / "empty").mkdir()
    (source / "deep" / "data").write_bytes(bytes(range(256)) * 100)
    archive = tmp_path / ("archive" + suffix)
    created = create_backup(source, archive, compression=compression)
    assert verify_archive(archive, created["manifest"]["sha256"])["valid"]
    assert not verify_archive(archive, "0" * 64)["valid"]
    restore_archive(archive, tmp_path / "out")
    assert (tmp_path / "out/source/deep/data").read_bytes() == bytes(range(256)) * 100
    assert (tmp_path / "out/source/empty").is_dir()


def test_dry_run_creates_nothing_and_destination_cannot_be_inside_source(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "data").write_text("data")
    destination = tmp_path / "not-created" / "backup.tar.gz"
    create_backup(source, destination, dry_run=True)
    assert not destination.parent.exists()
    with pytest.raises(ValueError, match="outside the source"):
        create_backup(source, source / "backup.tar.gz")
    assert not (source / "backup.tar.gz").exists()


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_backup_refuses_source_symlinks_without_publishing_partial_archive(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "link").symlink_to(tmp_path / "target")
    archive = tmp_path / "backup.tar.gz"
    with pytest.raises(ValueError, match="link or special"):
        create_backup(source, archive)
    assert not archive.exists()
    assert not list(tmp_path.glob("*.partial"))


def test_truncated_compressed_archive_fails_verification_and_restore(tmp_path):
    source = tmp_path / "data"
    source.write_bytes(os.urandom(4096))
    archive = tmp_path / "archive.tar.gz"
    create_backup(source, archive)
    archive.write_bytes(archive.read_bytes()[:-8])
    assert verify_archive(archive)["valid"] is False
    with pytest.raises((ValueError, EOFError, tarfile.TarError)):
        restore_archive(archive, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    result = CliRunner().invoke(app, ["backup", "verify", str(archive), "--json"])
    assert result.exit_code == 1
    assert json.loads(result.output)["valid"] is False


def test_backup_cli_json_create_and_restore(tmp_path):
    source = tmp_path / "one"
    source.write_text("hello")
    archive = tmp_path / "one.tar.gz"
    runner = CliRunner()
    created = runner.invoke(app, ["backup", "create", str(source), str(archive), "--json"])
    assert created.exit_code == 0
    assert json.loads(created.output)["file_count"] == 1
    restored = runner.invoke(
        app, ["backup", "restore", str(archive), str(tmp_path / "out"), "--json"]
    )
    assert restored.exit_code == 0
    assert json.loads(restored.output)["status"] == "restored"
    assert (tmp_path / "out/one").read_text() == "hello"


def test_interrupted_creation_never_publishes_archive(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "file").write_text("data")
    archive = tmp_path / "archive.tar.gz"
    original = tarfile.TarFile.addfile
    calls = 0

    def fail_on_file(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated interruption")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(tarfile.TarFile, "addfile", fail_on_file)
    with pytest.raises(OSError, match="simulated"):
        create_backup(source, archive)
    assert not archive.exists()
    assert not list(tmp_path.glob(".*.partial"))
    assert (source / "file").read_text() == "data"


def test_safe_restore_fails_closed_when_platform_lacks_required_primitives(tmp_path, monkeypatch):
    import forgekit.services.backup_service as backup

    source = tmp_path / "file"
    source.write_text("data")
    archive = tmp_path / "archive.tar"
    create_backup(source, archive, compression="none")
    monkeypatch.delattr(backup.os, "O_NOFOLLOW", raising=False)
    assert restore_archive(archive, tmp_path / "out", dry_run=True)["status"] == "dry_run"
    with pytest.raises(OSError, match="not supported"):
        restore_archive(archive, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_uncompressed_corruption_requires_trusted_checksum_to_detect_content_changes(tmp_path):
    source = tmp_path / "file"
    source.write_bytes(b"abcdefgh" * 1024)
    archive = tmp_path / "plain.tar"
    created = create_backup(source, archive, compression="none")
    with tarfile.open(archive) as tar:
        offset = tar.getmember("file").offset_data
    data = bytearray(archive.read_bytes())
    data[offset] ^= 1  # mutate file data, not a tar header
    archive.write_bytes(data)
    assert verify_archive(archive)["valid"] is True  # tar has no per-file checksum
    checked = verify_archive(archive, created["manifest"]["sha256"])
    assert checked["valid"] is False
    assert "SHA-256" in checked["errors"][0]
    archive.write_bytes(data[: offset + 512])
    assert verify_archive(archive)["valid"] is False


def test_hardlinked_source_files_are_stored_as_independent_files(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "one").write_text("contents")
    os.link(source / "one", source / "two")
    archive = tmp_path / "hardlinks.tar.gz"
    create_backup(source, archive)
    with tarfile.open(archive) as tar:
        assert tar.getmember("source/one").isfile()
        assert tar.getmember("source/two").isfile()
    restore_archive(archive, tmp_path / "out")
    assert (tmp_path / "out/source/one").read_text() == "contents"
    assert (tmp_path / "out/source/two").read_text() == "contents"


def test_restore_rejects_a_symlink_in_destination_ancestors(tmp_path):
    source = tmp_path / "source"
    source.write_text("data")
    archive = tmp_path / "data.tar"
    create_backup(source, archive, compression="none")
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "link").symlink_to(outside, target_is_directory=True)
    destination = tmp_path / "link" / "new-dir"
    for dry_run in (True, False):
        with pytest.raises(ValueError, match="symbolic link"):
            restore_archive(archive, destination, dry_run=dry_run, overwrite=True)
    assert list(outside.iterdir()) == []


def test_destination_ancestor_swap_is_never_followed(tmp_path, monkeypatch):
    import forgekit.services.backup_service as backup

    source = tmp_path / "source"
    source.write_text("data")
    archive = tmp_path / "data.tar"
    create_backup(source, archive, compression="none")
    parent = tmp_path / "parent"
    parent.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    original = backup._open_directory
    swapped = False

    def race(root_fd, parts):
        nonlocal swapped
        if not swapped:
            swapped = True
            parent.rename(tmp_path / "old-parent")
            parent.symlink_to(outside, target_is_directory=True)
        return original(root_fd, parts)

    monkeypatch.setattr(backup, "_open_directory", race)
    with pytest.raises(OSError):
        restore_archive(archive, parent / "dest", overwrite=True)
    assert list(outside.iterdir()) == []
    assert list((tmp_path / "old-parent").iterdir()) == []


def test_restore_uses_the_verified_snapshot_even_if_original_changes(tmp_path, monkeypatch):
    import forgekit.services.backup_service as backup

    source = tmp_path / "source"
    source.write_text("original")
    archive = tmp_path / "data.tar"
    create_backup(source, archive, compression="none")
    snapshot = backup._snapshot_archive

    def change_after_snapshot(raw, archive_path, scratch):
        snapshot(raw, archive_path, scratch)
        archive_path.write_bytes(b"changed after snapshot")

    monkeypatch.setattr(backup, "_snapshot_archive", change_after_snapshot)
    result = restore_archive(archive, tmp_path / "out")
    assert result["status"] == "restored"
    assert (tmp_path / "out/source").read_text() == "original"


def test_restore_rejects_path_replacement_during_snapshot(tmp_path, monkeypatch):
    import forgekit.services.backup_service as backup

    source = tmp_path / "source"
    source.write_text("original")
    archive = tmp_path / "data.tar"
    create_backup(source, archive, compression="none")
    replacement = tmp_path / "replacement"
    replacement.write_text("replacement")
    disk_usage = backup.shutil.disk_usage

    def change_path(folder):
        os.replace(replacement, archive)
        return disk_usage(folder)

    monkeypatch.setattr(backup.shutil, "disk_usage", change_path)
    with pytest.raises(ValueError, match="changed"):
        restore_archive(archive, tmp_path / "out")
    assert not (tmp_path / "out").exists()
    assert archive.read_text() == "replacement"


def test_dry_run_never_creates_scratch_and_low_space_fails_before_writes(tmp_path, monkeypatch):
    import forgekit.services.backup_service as backup

    source = tmp_path / "source"
    source.write_text("data")
    archive = tmp_path / "data.tar"
    create_backup(source, archive, compression="none")
    tempfile_open = backup.tempfile.TemporaryFile
    monkeypatch.setattr(
        backup.tempfile, "TemporaryFile", lambda **kwargs: pytest.fail("scratch created")
    )
    assert restore_archive(archive, tmp_path / "out", dry_run=True)["status"] == "dry_run"
    assert not (tmp_path / "out").exists()
    monkeypatch.setattr(backup.tempfile, "TemporaryFile", tempfile_open)
    monkeypatch.setattr(backup.shutil, "disk_usage", lambda _: type("Usage", (), {"free": 0})())
    with pytest.raises(OSError, match="temporary space"):
        restore_archive(archive, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_archive_resource_limits_reject_before_destination_writes(tmp_path, monkeypatch):
    import forgekit.services.backup_service as backup

    archive = tmp_path / "many.tar"
    make_tar(archive, [("one", tarfile.REGTYPE, b"1"), ("two", tarfile.REGTYPE, b"2")])
    monkeypatch.setattr(backup, "_MAX_MEMBERS", 1)
    assert verify_archive(archive)["valid"] is False
    with pytest.raises(ValueError, match="too many"):
        restore_archive(archive, tmp_path / "out", dry_run=True)
    assert not (tmp_path / "out").exists()
    monkeypatch.setattr(backup, "_MAX_MEMBERS", 100)
    monkeypatch.setattr(backup, "_MAX_PATH_PARTS", 2)
    make_tar(archive, [("a/b/c", tarfile.REGTYPE, b"1")])
    with pytest.raises(ValueError, match="nested too deeply"):
        restore_archive(archive, tmp_path / "out", dry_run=True)
    assert not (tmp_path / "out").exists()


def test_oversized_pax_metadata_rejected_without_extracting(tmp_path, monkeypatch):
    import forgekit.services.backup_service as backup

    archive = tmp_path / "pax.tar"
    make_tar(archive, [("x" * 200, tarfile.REGTYPE, b"data")])
    monkeypatch.setattr(backup, "_MAX_METADATA_BYTES", 128)
    result = verify_archive(archive)
    assert result["valid"] is False
    assert "metadata" in " ".join(result["errors"]).lower()
    with pytest.raises((ValueError, tarfile.ReadError)):
        restore_archive(archive, tmp_path / "out", dry_run=True)
    assert not (tmp_path / "out").exists()


def test_archive_fifo_is_rejected_without_blocking(tmp_path):
    if not hasattr(os, "mkfifo") or not hasattr(os, "O_NONBLOCK"):
        pytest.skip("non-blocking FIFOs unavailable")
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    with pytest.raises(ValueError, match="regular file"):
        restore_archive(fifo, tmp_path / "out")
    assert verify_archive(fifo)["valid"] is False


def test_creation_rejects_names_that_restore_cannot_accept(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "bad:name").write_text("data")
    archive = tmp_path / "bad.tar"
    for dry_run in (True, False):
        with pytest.raises(ValueError, match="Unsafe archive path"):
            create_backup(source, archive, compression="none", dry_run=dry_run)
        assert not archive.exists()
        assert not list(tmp_path.glob(".*.partial"))
    assert (source / "bad:name").read_text() == "data"


def test_creation_enforces_restore_member_limit_and_cleans_partial(tmp_path, monkeypatch):
    import forgekit.services.backup_service as backup

    source = tmp_path / "source"
    source.mkdir()
    (source / "file").write_text("data")
    archive = tmp_path / "bad.tar"
    monkeypatch.setattr(backup, "_MAX_MEMBERS", 1)
    for dry_run in (True, False):
        with pytest.raises(ValueError, match="too many"):
            create_backup(source, archive, compression="none", dry_run=dry_run)
        assert not archive.exists()
        assert not list(tmp_path.glob(".*.partial"))
    assert (source / "file").read_text() == "data"


def test_listing_labels_links_instead_of_misreporting_regular_files(tmp_path):
    from forgekit.services.backup_service import list_archive

    archive = tmp_path / "links.tar"
    make_tar(archive, [("link", tarfile.SYMTYPE, b"target")])
    assert list_archive(archive)[0]["type"] == "symlink"
    result = CliRunner().invoke(app, ["backup", "list", str(archive), "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output)[0]["type"] == "symlink"
    assert verify_archive(archive)["valid"] is False


@pytest.mark.parametrize("compression", ["gz", "bz2", "xz"])
def test_expanded_compression_limit_fails_before_restore_writes(tmp_path, monkeypatch, compression):
    import forgekit.services.backup_service as backup

    source = tmp_path / "source"
    source.write_bytes(b"x")
    archive = tmp_path / "data.tar"
    create_backup(source, archive, compression=compression)
    # The compressed stream is small, while the padded tar stream is 10 KiB.
    assert archive.stat().st_size < 1000
    monkeypatch.setattr(backup, "_MAX_EXPANDED_BYTES", 1000)
    result = verify_archive(archive)
    assert result["valid"] is False and "expanded size" in " ".join(result["errors"])
    with pytest.raises(ValueError, match="expanded size"):
        restore_archive(archive, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_gnu_sparse_member_is_rejected(tmp_path):
    archive = tmp_path / "sparse.tar"
    member = tarfile.TarInfo("sparse")
    member.type = tarfile.GNUTYPE_SPARSE
    archive.write_bytes(member.tobuf(format=tarfile.GNU_FORMAT) + bytes(1024))
    result = verify_archive(archive)
    assert result["valid"] is False
    assert "sparse" in " ".join(result["errors"]).lower()
    with pytest.raises((ValueError, tarfile.ReadError)):
        restore_archive(archive, tmp_path / "out", dry_run=True)
    assert not (tmp_path / "out").exists()
