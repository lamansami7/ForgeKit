"""Streaming backups and conservative, non-following archive restoration.

Archives are untrusted input.  Restore accepts regular files and directories only;
links, devices and ambiguous paths are rejected rather than silently skipped.
"""

from __future__ import annotations

import bz2
import gzip
import hashlib
import lzma
import os
import shutil
import stat
import tarfile
import tempfile
import time
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Callable, Iterator

_CHUNK_SIZE = 1024 * 1024
# Defensive limits for untrusted archives. They also bound in-memory indexes.
_MAX_MEMBERS = 100_000
_MAX_METADATA_BYTES = 1024 * 1024
_MAX_MEMBER_PATH = 4096
_MAX_PATH_PARTS = 128
_MAX_EXPANDED_BYTES = 1024**4  # 1 TiB of expanded data, including tar headers.
_SCRATCH_RESERVE_BYTES = 64 * 1024 * 1024


class _BoundedTarInfo(tarfile.TarInfo):
    """Reject oversized metadata before tarfile allocates a PAX/GNU header."""

    def _proc_member(self, tar: tarfile.TarFile) -> tarfile.TarInfo:
        if self.type in (
            tarfile.XHDTYPE,
            tarfile.XGLTYPE,
            tarfile.SOLARIS_XHDTYPE,
            tarfile.GNUTYPE_LONGNAME,
            tarfile.GNUTYPE_LONGLINK,
        ) and (self.size < 0 or self.size > _MAX_METADATA_BYTES):
            raise tarfile.ReadError("Archive metadata header exceeds the safety limit")
        if self.type == tarfile.GNUTYPE_SPARSE:
            raise tarfile.ReadError("Sparse archive members are not supported")
        return super()._proc_member(tar)


def _open_tar(stream: BinaryIO) -> tarfile.TarFile:
    stream.seek(0)
    return tarfile.open(fileobj=stream, mode="r:*", tarinfo=_BoundedTarInfo)


def _archive_fingerprint(stream: BinaryIO) -> tuple[int, int, int, int, int]:
    st = os.fstat(stream.fileno())
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def _open_archive(archive: Path) -> BinaryIO:
    """Open a regular file without blocking on a substituted FIFO or device."""
    fd = os.open(archive, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError(f"Archive is not a regular file: {archive}")
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


def _snapshot_archive(source: BinaryIO, archive: Path, scratch: BinaryIO) -> None:
    """Copy an opened archive to private scratch storage before any restore writes."""
    before = _archive_fingerprint(source)
    size = before[2]
    if size > _MAX_EXPANDED_BYTES:
        raise ValueError("Archive size exceeds the safety limit")
    free = shutil.disk_usage(tempfile.gettempdir()).free
    if size > max(0, free - _SCRATCH_RESERVE_BYTES):
        raise OSError("Insufficient temporary space to snapshot the archive safely")
    source.seek(0)
    remaining = size
    while remaining:
        chunk = source.read(min(remaining, _CHUNK_SIZE))
        if not chunk:
            raise ValueError("Archive changed or was truncated while being copied")
        scratch.write(chunk)
        remaining -= len(chunk)
    if source.read(1) or _archive_fingerprint(source) != before:
        raise ValueError("Archive changed while being copied")
    try:
        st = archive.stat()
    except OSError as exc:
        raise ValueError("Archive path changed while being copied") from exc
    if (st.st_dev, st.st_ino) != before[:2]:
        raise ValueError("Archive path changed while being copied")
    scratch.flush()
    scratch.seek(0)


def _archive_parts(name: str) -> tuple[str, ...]:
    if (
        not name
        or name.startswith("/")
        or "\\" in name
        or ":" in name
        or "\x00" in name
        or ".." in name.split("/")
    ):
        raise ValueError(f"Unsafe archive path: {name!r}")
    if len(name) > _MAX_MEMBER_PATH:
        raise ValueError("Archive member path exceeds the safety limit")
    parts = PurePosixPath(name).parts
    if len(parts) > _MAX_PATH_PARTS:
        raise ValueError("Archive member path is nested too deeply")
    return parts


def _source_details(
    item: Path, source: Path, index: int, total: int
) -> tuple[str, os.stat_result, int]:
    if index >= _MAX_MEMBERS:
        raise ValueError("Backup has too many members to restore safely")
    name = item.relative_to(source.parent).as_posix()
    if not _archive_parts(name):
        raise ValueError(f"Unsafe source path: {item}")
    st = item.lstat()
    if stat.S_ISREG(st.st_mode):
        total += st.st_size
        if total > _MAX_EXPANDED_BYTES:
            raise ValueError("Backup expanded size exceeds the safety limit")
    elif not stat.S_ISDIR(st.st_mode):
        raise ValueError(f"Backup source contains a link or special file: {item}")
    return name, st, total


def compression_mode(comp: str) -> str:
    try:
        return {"gz": "w:gz", "bz2": "w:bz2", "xz": "w:xz", "none": "w"}[comp]
    except KeyError as exc:
        raise ValueError(f"Unsupported compression: {comp}") from exc


def extension_for(comp: str) -> str:
    compression_mode(comp)  # validate instead of silently choosing gzip
    return {"gz": ".tar.gz", "bz2": ".tar.bz2", "xz": ".tar.xz", "none": ".tar"}[comp]


def _source_items(source: Path) -> Iterator[Path]:
    """Yield all entries without following links; fail rather than omit data."""

    def validate(path: Path) -> None:
        mode = path.lstat().st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            raise ValueError(f"Backup source contains a link or special file: {path}")

    validate(source)
    yield source
    if not source.is_dir():
        return

    def onerror(error: OSError) -> None:
        raise error

    for directory, dirs, files in os.walk(source, topdown=True, followlinks=False, onerror=onerror):
        dirs.sort()
        files.sort()
        for name in dirs + files:
            item = Path(directory) / name
            validate(item)
            yield item


def _archive_path(source: Path, destination: Path, compression: str) -> Path:
    if destination.is_dir() or not str(destination).endswith(
        (".tar.gz", ".tar.bz2", ".tar.xz", ".tar", ".gz", ".bz2", ".xz")
    ):
        return (
            destination
            / f"{source.name}-{time.strftime('%Y%m%d-%H%M%S')}{extension_for(compression)}"
        )
    return destination


def create_backup(
    source: Path,
    destination: Path,
    compression: str = "gz",
    dry_run: bool = False,
    progress_callback: Callable | None = None,
) -> dict[str, object]:
    mode = compression_mode(compression)
    source = Path(source).expanduser().absolute()
    destination = Path(destination).expanduser().absolute()
    if not source.exists() and not source.is_symlink():
        raise FileNotFoundError(f"Source not found: {source}")
    if not source.name:
        raise ValueError(
            "Backing up a filesystem root is not supported; choose a directory within it"
        )
    archive = _archive_path(source, destination, compression)
    source_resolved = source.resolve()
    archive_resolved = archive.resolve()
    if archive_resolved == source_resolved or (
        source.is_dir() and archive_resolved.is_relative_to(source_resolved)
    ):
        raise ValueError("Backup destination must be outside the source")
    if archive.exists() or archive.is_symlink():
        raise FileExistsError(f"Archive already exists: {archive}")

    if dry_run:
        count = 0
        total = 0
        for index, item in enumerate(_source_items(source)):
            _, st, total = _source_details(item, source, index, total)
            if stat.S_ISREG(st.st_mode):
                count += 1
        return {
            "dry_run": True,
            "source": str(source),
            "archive": str(archive),
            "compression": compression,
            "estimated_size": total,
            "file_count": count,
        }

    archive.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(
        prefix=f".{archive.name}.", suffix=".partial", dir=archive.parent
    )
    temp_path = Path(temp_name)
    count = 0
    total = 0
    start = time.monotonic()
    try:
        with os.fdopen(fd, "w+b") as output, tarfile.open(fileobj=output, mode=mode) as tar:
            for index, item in enumerate(_source_items(source)):
                relative, st, total = _source_details(item, source, index, total)
                if stat.S_ISDIR(st.st_mode):
                    info = tar.gettarinfo(str(item), arcname=relative)
                    if not info.isdir():
                        raise ValueError(f"Source changed while backing up: {item}")
                    tar.addfile(info)
                elif stat.S_ISREG(st.st_mode):
                    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                    file_fd = os.open(item, flags)
                    with os.fdopen(file_fd, "rb") as stream:
                        actual = os.fstat(stream.fileno())
                        if (
                            not stat.S_ISREG(actual.st_mode)
                            or (actual.st_dev, actual.st_ino) != (st.st_dev, st.st_ino)
                            or actual.st_size != st.st_size
                            or actual.st_mtime_ns != st.st_mtime_ns
                        ):
                            raise ValueError(f"Source changed while backing up: {item}")
                        info = tar.gettarinfo(str(item), arcname=relative)
                        # Store hard-linked files as independent regular files.
                        info.type = tarfile.REGTYPE
                        info.linkname = ""
                        info.size = actual.st_size
                        tar.addfile(info, stream)
                        count += 1
                        if progress_callback and count % 50 == 0:
                            progress_callback(count)
                else:
                    raise ValueError(f"Source changed while backing up: {item}")
            output.flush()
        checksum = file_sha256(temp_path)
        # Hard-link publication is atomic and fails if another process created the
        # destination. The temporary file is on the same filesystem.
        os.link(temp_path, archive)
    finally:
        temp_path.unlink(missing_ok=True)

    elapsed = round(time.monotonic() - start, 2)
    size = archive.stat().st_size
    manifest = {
        "source": str(source),
        "archive": str(archive),
        "compression": compression,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "file_count": count,
        "total_bytes": total,
        "archive_size": size,
        "elapsed_seconds": elapsed,
        "sha256": checksum,
    }
    return {
        "archive": str(archive),
        "compression": compression,
        "file_count": count,
        "total_bytes": total,
        "archive_size": size,
        "elapsed_seconds": elapsed,
        "manifest": manifest,
    }


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def _member_details(member: tarfile.TarInfo) -> dict[str, object]:
    kind = (
        "directory"
        if member.isdir()
        else "file"
        if member.isfile() and member.sparse is None
        else "symlink"
        if member.issym()
        else "hardlink"
        if member.islnk()
        else "special"
    )
    return {
        "name": member.name,
        "size": member.size,
        "is_dir": member.isdir(),
        "type": kind,
        "mtime": member.mtime,
        "mode": oct(member.mode),
    }


def list_archive(archive: Path) -> list[dict[str, object]]:
    """List without extracting, with the same parser resource limits as restore."""
    try:
        with _open_archive(Path(archive)) as stream, _open_tar(stream) as tar:
            result = []
            for index, member in enumerate(tar):
                if index >= _MAX_MEMBERS:
                    raise ValueError("Archive has too many members")
                result.append(_member_details(member))
            return result
    except RecursionError as exc:
        raise ValueError("Archive metadata is nested too deeply") from exc


def _safe_members(tar: tarfile.TarFile) -> list[tuple[tarfile.TarInfo, tuple[str, ...]]]:
    result: list[tuple[tarfile.TarInfo, tuple[str, ...]]] = []
    seen: dict[tuple[str, ...], bool] = {}
    required_dirs: set[tuple[str, ...]] = set()
    total_size = 0
    for index, member in enumerate(tar):
        if index >= _MAX_MEMBERS:
            raise ValueError("Archive has too many members")
        name = member.name
        parts = _archive_parts(name)
        if member.size < 0:
            raise ValueError(f"Invalid archive member size: {name!r}")
        if member.isfile():
            if member.sparse is not None:
                raise ValueError(f"Sparse archive member is not supported: {name!r}")
            total_size += member.size
            if total_size > _MAX_EXPANDED_BYTES:
                raise ValueError("Archive expanded size exceeds the safety limit")
        if not parts and member.isdir():
            continue  # a conventional './' root entry
        if not parts or not (member.isfile() or member.isdir()):
            raise ValueError(
                f"Unsupported archive member (only files and directories allowed): {name!r}"
            )
        if parts in seen:
            raise ValueError(f"Duplicate archive path: {name!r}")
        for i in range(1, len(parts)):
            if seen.get(parts[:i]) is False:
                raise ValueError(f"Archive file is used as a parent directory: {name!r}")
        if member.isfile() and parts in required_dirs:
            raise ValueError(f"Archive file is used as a parent directory: {name!r}")
        required_dirs.update(parts[:i] for i in range(1, len(parts)))
        seen[parts] = member.isdir()
        result.append((member, parts))
    return result


def _check_compression(raw: BinaryIO) -> None:
    """Read compressed streams to EOF to validate trailers, subject to a size cap."""
    raw.seek(0)
    magic = raw.read(6)
    raw.seek(0)
    opener = (
        gzip.GzipFile
        if magic.startswith(b"\x1f\x8b")
        else bz2.BZ2File
        if magic.startswith(b"BZh")
        else lzma.LZMAFile
        if magic.startswith(b"\xfd7zXZ\x00")
        else None
    )
    if opener:
        expanded = 0
        if opener is gzip.GzipFile:
            stream = opener(fileobj=raw, mode="rb")
        else:
            stream = opener(raw, mode="rb")
        with stream:
            while chunk := stream.read(_CHUNK_SIZE):
                expanded += len(chunk)
                if expanded > _MAX_EXPANDED_BYTES:
                    raise ValueError("Archive expanded size exceeds the safety limit")


def _verify_stream(raw: BinaryIO, expected_sha256: str | None = None) -> tuple[int, str]:
    if expected_sha256 is not None and (
        len(expected_sha256) != 64
        or any(c not in "0123456789abcdefABCDEF" for c in expected_sha256)
    ):
        raise ValueError("Expected SHA-256 must be 64 hexadecimal characters")
    before = _archive_fingerprint(raw)
    if before[2] > _MAX_EXPANDED_BYTES:
        raise ValueError("Archive size exceeds the safety limit")
    raw.seek(0)
    digest = hashlib.sha256()
    for chunk in iter(lambda: raw.read(_CHUNK_SIZE), b""):
        digest.update(chunk)
    actual_sha256 = digest.hexdigest()
    if expected_sha256 and actual_sha256.lower() != expected_sha256.lower():
        raise ValueError("SHA-256 does not match the expected checksum")
    with _open_tar(raw) as tar:
        members = _safe_members(tar)
        for member, _ in members:
            if member.isfile():
                stream = tar.extractfile(member)
                if stream is None:
                    raise tarfile.ReadError(f"Cannot read {member.name}")
                with stream:
                    while stream.read(_CHUNK_SIZE):
                        pass
    _check_compression(raw)
    if _archive_fingerprint(raw) != before:
        raise ValueError("Archive changed during verification")
    return len(members), actual_sha256


def verify_archive(archive: Path, expected_sha256: str | None = None) -> dict[str, object]:
    archive = Path(archive)
    if not archive.exists():
        raise FileNotFoundError(f"Archive not found: {archive}")
    try:
        with _open_archive(archive) as raw:
            opened = _archive_fingerprint(raw)
            member_count, actual_sha256 = _verify_stream(raw, expected_sha256)
            current = archive.stat()
            if (current.st_dev, current.st_ino) != opened[:2]:
                raise ValueError("Archive path changed during verification")
        return {
            "archive": str(archive),
            "valid": True,
            "member_count": member_count,
            "errors": [],
            "sha256": actual_sha256,
        }
    except (tarfile.TarError, OSError, EOFError, ValueError, lzma.LZMAError, RecursionError) as exc:
        return {"archive": str(archive), "valid": False, "member_count": 0, "errors": [str(exc)]}


def _check_existing(
    destination: Path, members: list[tuple[tarfile.TarInfo, tuple[str, ...]]]
) -> list[str]:
    conflicts: list[str] = []
    # Reject symlinks in the destination itself *and* any existing ancestor.
    current = Path(destination.anchor)
    for part in destination.parts[1:]:
        current /= part
        try:
            st = current.lstat()
        except FileNotFoundError:
            break
        if stat.S_ISLNK(st.st_mode):
            raise ValueError(f"Refusing to restore through a symbolic link: {current}")
        if not stat.S_ISDIR(st.st_mode):
            raise ValueError(f"Expected a directory: {current}")
    for member, parts in members:
        path = destination
        for index, part in enumerate(parts):
            path = path / part
            try:
                st = path.lstat()
            except FileNotFoundError:
                break
            if stat.S_ISLNK(st.st_mode):
                raise ValueError(f"Refusing to restore through a symbolic link: {path}")
            is_last = index == len(parts) - 1
            if not is_last or member.isdir():
                if not stat.S_ISDIR(st.st_mode):
                    raise ValueError(f"Expected a directory: {path}")
            elif not stat.S_ISREG(st.st_mode):
                raise ValueError(f"Refusing to overwrite non-regular file: {path}")
            else:
                conflicts.append(str(path))
    return conflicts


def _open_directory(root_fd: int, parts: tuple[str, ...]) -> int:
    fd = os.dup(root_fd)
    try:
        for part in parts:
            try:
                os.mkdir(part, 0o755, dir_fd=fd)
            except FileExistsError:
                pass
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _restore_file(
    tar: tarfile.TarFile, member: tarfile.TarInfo, parent_fd: int, name: str, overwrite: bool
) -> None:
    # Create an unpredictable file in the destination directory, then publish it
    # without following links. No-overwrite uses an atomic hard link.
    import secrets

    temp_name = f".forgekit-{secrets.token_hex(16)}.partial"
    fd = os.open(
        temp_name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd
    )
    try:
        source = tar.extractfile(member)
        if source is None:
            raise tarfile.ReadError(f"Cannot read {member.name}")
        with source, os.fdopen(fd, "wb") as output:
            fd = -1
            shutil.copyfileobj(source, output, _CHUNK_SIZE)
            output.flush()
            os.fchmod(output.fileno(), member.mode & 0o777)
        if overwrite:
            try:
                existing = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                if not stat.S_ISREG(existing.st_mode):
                    raise ValueError(f"Refusing to overwrite non-regular file: {name}")
            except FileNotFoundError:
                pass
            os.replace(temp_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        else:
            os.link(
                temp_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False
            )
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(temp_name, dir_fd=parent_fd)
        except FileNotFoundError:
            pass


def _restore_plan(
    tar: tarfile.TarFile, archive: Path, destination: Path
) -> tuple[list[tuple[tarfile.TarInfo, tuple[str, ...]]], dict[str, object]]:
    members = _safe_members(tar)
    conflicts = _check_existing(destination, members)
    archive_names = {Path(os.path.abspath(archive)), archive.resolve()}
    if any(destination.joinpath(*parts) in archive_names for _, parts in members):
        raise ValueError("Restore would overwrite the archive itself")
    return members, {
        "archive": str(archive),
        "destination": str(destination),
        "total_members": len(members),
        "would_overwrite": conflicts[:20],
        "conflict_count": len(conflicts),
    }


def restore_archive(
    archive: Path,
    destination: Path,
    dry_run: bool = False,
    overwrite: bool = False,
) -> dict[str, object]:
    archive = Path(archive).expanduser().absolute()
    destination = Path(os.path.abspath(Path(destination).expanduser()))
    if not archive.exists():
        raise FileNotFoundError(f"Archive not found: {archive}")
    try:
        with _open_archive(archive) as source:
            # The preliminary plan is read-only. In particular, a dry run never
            # creates a scratch file, a destination, or any destination parents.
            with _open_tar(source) as tar:
                members, base = _restore_plan(tar, archive, destination)
                if dry_run:
                    return {
                        **base,
                        "status": "dry_run",
                        "members": [_member_details(m) for m, _ in members[:20]],
                    }
                if base["conflict_count"] and not overwrite:
                    return {
                        **base,
                        "status": "needs_confirmation",
                        "message": f"{base['conflict_count']} files would be overwritten; pass --force",
                    }
            # Fail closed on platforms without the directory-relative primitives
            # needed to avoid symlink races. Inspection and dry runs still work.
            if not (
                hasattr(os, "O_NOFOLLOW")
                and hasattr(os, "O_DIRECTORY")
                and hasattr(os, "fchmod")
                and os.open in os.supports_dir_fd
                and os.mkdir in os.supports_dir_fd
                and os.link in os.supports_dir_fd
                and os.stat in os.supports_dir_fd
                and os.unlink in os.supports_dir_fd
                and os.rename in os.supports_dir_fd
                and os.stat in os.supports_follow_symlinks
                and os.link in os.supports_follow_symlinks
            ):
                raise OSError("Safe restore is not supported on this platform")
            # A private temporary snapshot ensures that the exact bytes verified
            # below are the bytes extracted, even if the source path is replaced.
            with tempfile.TemporaryFile(mode="w+b") as scratch:
                _snapshot_archive(source, archive, scratch)
                try:
                    _verify_stream(scratch)
                except (tarfile.TarError, OSError, EOFError, ValueError, lzma.LZMAError) as exc:
                    raise ValueError(f"Archive verification failed: {exc}") from exc
                with _open_tar(scratch) as tar:
                    members, base = _restore_plan(tar, archive, destination)
                    # Destination state could have changed while copying/verifying.
                    if base["conflict_count"] and not overwrite:
                        return {
                            **base,
                            "status": "needs_confirmation",
                            "message": f"{base['conflict_count']} files would be overwritten; pass --force",
                        }
                    anchor_fd = os.open(
                        destination.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                    )
                    try:
                        root_fd = _open_directory(anchor_fd, destination.parts[1:])
                    finally:
                        os.close(anchor_fd)
                    try:
                        for member, parts in members:
                            if member.isdir():
                                fd = _open_directory(root_fd, parts)
                                os.close(fd)
                            else:
                                fd = _open_directory(root_fd, parts[:-1])
                                try:
                                    _restore_file(tar, member, fd, parts[-1], overwrite)
                                finally:
                                    os.close(fd)
                    finally:
                        os.close(root_fd)
        return {**base, "restored": len(members), "status": "restored"}
    except RecursionError as exc:
        raise ValueError("Archive metadata is nested too deeply") from exc
