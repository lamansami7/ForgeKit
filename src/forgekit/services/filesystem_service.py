"""Read-only filesystem scanning without following symlinks by default."""

import hashlib
import heapq
import logging
import os
import stat
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)


def _walk(root: Path, exclusions: set[str], follow_symlinks: bool = False) -> Iterator:
    def onerror(exc: OSError) -> None:
        logger.warning("Could not scan %s: %s", exc.filename or root, exc)

    visited: set[tuple[int, int]] = set()
    for directory, dirs, files in os.walk(
        root, topdown=True, followlinks=follow_symlinks, onerror=onerror
    ):
        dirs[:] = sorted(d for d in dirs if d not in exclusions)
        files.sort()
        if follow_symlinks:
            try:
                info = os.stat(directory)
            except OSError as exc:
                onerror(exc)
                dirs[:] = []
                continue
            key = (info.st_dev, info.st_ino)
            if key in visited:
                dirs[:] = []
                continue
            visited.add(key)
        yield Path(directory), dirs, files


def _regular_size(path: Path, follow_symlinks: bool = False) -> int | None:
    try:
        info = path.stat() if follow_symlinks else path.lstat()
        return info.st_size if stat.S_ISREG(info.st_mode) else None
    except OSError as exc:
        logger.warning("Could not inspect %s: %s", path, exc)
        return None


def find_large_files(
    root: Path,
    threshold_bytes: int = 100 * 1024 * 1024,
    exclude_dirs: set[str] | None = None,
    follow_symlinks: bool = False,
    limit: int = 50,
) -> list[dict[str, object]]:
    if threshold_bytes < 0 or limit < 1:
        raise ValueError("Threshold must be non-negative and limit must be positive")
    # Keep only the largest `limit` entries, rather than every matching file.
    largest: list[tuple[int, str]] = []
    for directory, _, files in _walk(root, exclude_dirs or set(), follow_symlinks):
        for name in files:
            path = directory / name
            size = _regular_size(path, follow_symlinks)
            if size is not None and size >= threshold_bytes:
                entry = (size, str(path))
                if len(largest) < limit:
                    heapq.heappush(largest, entry)
                else:
                    heapq.heappushpop(largest, entry)
    return [
        {"path": path, "size": size, "name": Path(path).name}
        for size, path in sorted(largest, reverse=True)
    ]


def search_files(
    root: Path,
    query: str,
    exclude_dirs: set[str] | None = None,
    by_extension: bool = False,
    limit: int = 100,
) -> list[dict[str, object]]:
    if limit < 1:
        raise ValueError("Limit must be positive")
    q = query.lower()
    if by_extension:
        q = q.removeprefix("*")
        if not q.startswith("."):
            q = "." + q
    results: list[dict[str, object]] = []
    for directory, dirs, files in _walk(root, exclude_dirs or set()):
        for name in files:
            if name.lower().endswith(q) if by_extension else q in name.lower():
                path = directory / name
                size = _regular_size(path)
                if size is not None:
                    results.append({"path": str(path), "name": name, "size": size})
                    if len(results) >= limit:
                        return results
        if not by_extension:
            for name in dirs:
                path = directory / name
                if q in name.lower() and not path.is_symlink():
                    results.append({"path": str(path), "name": name, "size": 0, "is_dir": True})
                    if len(results) >= limit:
                        return results
    return results


def directory_size(root: Path, exclude_dirs: set[str] | None = None) -> dict[str, object]:
    total = 0
    count = 0
    directories = 0
    largest: list[tuple[int, str]] = []
    breakdown: dict[str, dict[str, object]] = {}
    for directory, dirs, files in _walk(root, exclude_dirs or set()):
        directories += 1
        if directory == root:
            for name in dirs:
                path = directory / name
                if not path.is_symlink():
                    breakdown[name] = {"name": name, "path": str(path), "size": 0, "is_dir": True}
        for name in files:
            path = directory / name
            size = _regular_size(path)
            if size is None:
                continue
            total += size
            count += 1
            entry = (size, str(path))
            if len(largest) < 10:
                heapq.heappush(largest, entry)
            else:
                heapq.heappushpop(largest, entry)
            relative = path.relative_to(root)
            child = relative.parts[0]
            if len(relative.parts) == 1:
                breakdown[child] = {"name": child, "path": str(path), "size": size, "is_dir": False}
            elif child in breakdown:
                breakdown[child]["size"] += size
    return {
        "path": str(root),
        "total_size": total,
        "file_count": count,
        "dir_count": directories,
        "largest_files": [{"path": p, "size": s} for s, p in sorted(largest, reverse=True)],
        "breakdown": sorted(breakdown.values(), key=lambda v: v["size"], reverse=True)[:20],
    }


def find_empty_dirs(root: Path, exclude_dirs: set[str] | None = None) -> list[str]:
    empty: list[str] = []
    for directory, _, _ in _walk(root, exclude_dirs or set()):
        try:
            with os.scandir(directory) as entries:
                if next(entries, None) is None:
                    empty.append(str(directory))
        except OSError as exc:
            logger.warning("Could not inspect %s: %s", directory, exc)
    return empty


def find_duplicates(
    root: Path, exclude_dirs: set[str] | None = None, min_size: int = 1, limit_groups: int = 20
) -> list[dict[str, object]]:
    if min_size < 0 or limit_groups < 1:
        raise ValueError("Minimum size must be non-negative and limit must be positive")
    by_size: dict[int, list[Path]] = {}
    for directory, _, files in _walk(root, exclude_dirs or set()):
        for name in files:
            path = directory / name
            size = _regular_size(path)
            if size is not None and size >= min_size:
                by_size.setdefault(size, []).append(path)
    duplicates: list[dict[str, object]] = []
    for size, paths in by_size.items():
        if len(paths) < 2:
            continue
        hashes: dict[str, list[str]] = {}
        for path in paths:
            try:
                digest = file_hash(path)
                hashes.setdefault(digest, []).append(str(path))
            except OSError as exc:
                logger.warning("Could not hash %s: %s", path, exc)
        for digest, group in hashes.items():
            if len(group) > 1:
                duplicates.append(
                    {"hash": digest, "size": size, "files": group, "count": len(group)}
                )
    duplicates.sort(key=lambda item: item["size"], reverse=True)
    return duplicates[:limit_groups]


def file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()
