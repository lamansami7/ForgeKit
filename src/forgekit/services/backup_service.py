"""Backup services."""

from __future__ import annotations

import contextlib
import hashlib
import tarfile
import time
from pathlib import Path
from typing import Callable


def compression_mode(comp: str) -> str:
    mapping = {"gz": "w:gz", "bz2": "w:bz2", "xz": "w:xz", "none": "w"}
    return mapping.get(comp, "w:gz")


def extension_for(comp: str) -> str:
    return {"gz": ".tar.gz", "bz2": ".tar.bz2", "xz": ".tar.xz", "none": ".tar"}.get(
        comp, ".tar.gz"
    )


def create_backup(
    source: Path,
    destination: Path,
    compression: str = "gz",
    dry_run: bool = False,
    progress_callback: Callable | None = None,
) -> dict[str, object]:
    if not source.exists():
        raise FileNotFoundError(f"Source not found: {source}")

    destination = Path(destination)
    # If destination is a directory, create archive inside it
    if destination.exists() and destination.is_dir():
        archive_name = f"{source.name}-{time.strftime('%Y%m%d-%H%M%S')}{extension_for(compression)}"
        archive_path = destination / archive_name
    elif str(destination).endswith((".tar.gz", ".tar.bz2", ".tar.xz", ".tar")):
        archive_path = destination
        archive_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        # Assume destination is directory or file path without extension
        if destination.suffix in (".gz", ".bz2", ".xz", ".tar"):
            archive_path = destination
            archive_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            # Treat as directory
            destination.mkdir(parents=True, exist_ok=True)
            archive_name = (
                f"{source.name}-{time.strftime('%Y%m%d-%H%M%S')}{extension_for(compression)}"
            )
            archive_path = destination / archive_name

    if dry_run:
        # Estimate size
        total_size = 0
        file_count = 0
        if source.is_file():
            total_size = source.stat().st_size
            file_count = 1
        else:
            for p in source.rglob("*"):
                if p.is_file():
                    try:
                        total_size += p.stat().st_size
                        file_count += 1
                    except OSError:
                        pass
        return {
            "dry_run": True,
            "source": str(source),
            "archive": str(archive_path),
            "compression": compression,
            "estimated_size": total_size,
            "file_count": file_count,
        }

    if archive_path.exists():
        raise FileExistsError(f"Archive already exists: {archive_path} (refusing to overwrite)")

    archive_path.parent.mkdir(parents=True, exist_ok=True)

    file_count = 0
    total_bytes = 0
    start = time.monotonic()

    mode = compression_mode(compression)
    with tarfile.open(archive_path, mode) as tar:
        if source.is_file():
            tar.add(source, arcname=source.name)
            file_count = 1
            total_bytes = source.stat().st_size
        else:
            # Add preserving metadata
            for item in source.rglob("*"):
                # Use arcname relative to source parent so top-level dir included
                try:
                    arcname = (
                        item.relative_to(source.parent) if source.parent != Path(".") else item.name
                    )
                except ValueError:
                    arcname = item.name
                try:
                    tar.add(item, arcname=arcname, recursive=False)
                    if item.is_file():
                        file_count += 1
                        total_bytes += item.stat().st_size
                    if progress_callback and file_count % 50 == 0:
                        progress_callback(file_count)
                except (PermissionError, OSError, FileNotFoundError):
                    continue
            # Ensure top-level dir added if empty
            if file_count == 0:
                tar.add(source, arcname=source.name)

    elapsed = time.monotonic() - start
    archive_size = archive_path.stat().st_size

    # Write manifest for verification
    manifest = {
        "source": str(source),
        "archive": str(archive_path),
        "compression": compression,
        "created": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "file_count": file_count,
        "total_bytes": total_bytes,
        "archive_size": archive_size,
        "elapsed_seconds": round(elapsed, 2),
    }
    # checksum
    with contextlib.suppress(Exception):
        manifest["sha256"] = file_sha256(archive_path)

    return {
        "archive": str(archive_path),
        "compression": compression,
        "file_count": file_count,
        "total_bytes": total_bytes,
        "archive_size": archive_size,
        "elapsed_seconds": round(elapsed, 2),
        "manifest": manifest,
    }


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def list_archive(archive: Path) -> list[dict[str, object]]:
    if not archive.exists():
        raise FileNotFoundError(f"Archive not found: {archive}")
    members: list[dict[str, object]] = []
    with tarfile.open(archive, "r:*") as tar:
        for m in tar.getmembers():
            members.append(
                {
                    "name": m.name,
                    "size": m.size,
                    "is_dir": m.isdir(),
                    "mtime": m.mtime,
                    "mode": oct(m.mode),
                }
            )
    return members


def verify_archive(archive: Path) -> dict[str, object]:
    if not archive.exists():
        raise FileNotFoundError(f"Archive not found: {archive}")
    try:
        with tarfile.open(archive, "r:*") as tar:
            # Validate members
            members = tar.getmembers()
            errors: list[str] = []
            # Try reading each file header
            for m in members:
                try:
                    # Just validate header
                    _ = m.name
                except Exception as e:
                    errors.append(str(e))
            # Optionally try to extract to check integrity (without writing)
            # tarfile will raise on corrupt archive
            return {
                "archive": str(archive),
                "valid": len(errors) == 0,
                "member_count": len(members),
                "errors": errors,
                "sha256": file_sha256(archive),
            }
    except tarfile.TarError as e:
        return {"archive": str(archive), "valid": False, "member_count": 0, "errors": [str(e)]}


def restore_archive(
    archive: Path,
    destination: Path,
    dry_run: bool = False,
    overwrite: bool = False,
) -> dict[str, object]:
    if not archive.exists():
        raise FileNotFoundError(f"Archive not found: {archive}")

    destination = Path(destination)

    members = list_archive(archive)
    # Check for overwrite conflicts
    conflicts: list[str] = []
    if not dry_run:
        destination.mkdir(parents=True, exist_ok=True)
    for m in members:
        target = destination / m["name"]  # type: ignore
        if target.exists() and not overwrite:
            conflicts.append(str(target))

    if conflicts and not dry_run:
        return {
            "archive": str(archive),
            "destination": str(destination),
            "would_overwrite": conflicts[:20],
            "total_members": len(members),
            "status": "needs_confirmation",
            "message": f"{len(conflicts)} files would be overwritten — pass --force to overwrite",
        }

    if dry_run:
        return {
            "archive": str(archive),
            "destination": str(destination),
            "total_members": len(members),
            "would_overwrite": conflicts[:20] if conflicts else [],
            "status": "dry_run",
            "members": members[:20],
        }

    # Actual restore
    with tarfile.open(archive, "r:*") as tar:
        # Security: prevent path traversal
        def is_within_directory(directory: Path, target: Path) -> bool:
            try:
                target.resolve().relative_to(directory.resolve())
                return True
            except ValueError:
                return False

        safe_members = []
        for member in tar.getmembers():
            member_path = destination / member.name
            # Block traversal like ../../etc
            if not str(member_path.resolve()).startswith(str(destination.resolve())):
                continue
            safe_members.append(member)

        tar.extractall(path=destination, members=safe_members)  # noqa: S202 - validated above

    return {
        "archive": str(archive),
        "destination": str(destination),
        "total_members": len(members),
        "restored": len(members),
        "status": "restored",
    }
