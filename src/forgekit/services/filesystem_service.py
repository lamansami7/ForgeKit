"""Filesystem scanning services."""

import contextlib
import hashlib
import os
from pathlib import Path


def find_large_files(
    root: Path,
    threshold_bytes: int = 100 * 1024 * 1024,
    exclude_dirs: set[str] | None = None,
    follow_symlinks: bool = False,
    limit: int = 50,
) -> list[dict[str, object]]:
    exclude_dirs = exclude_dirs or set()
    large: list[dict[str, object]] = []
    visited_inodes: set[tuple[int, int]] = set()

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=follow_symlinks):
        # Exclude dirs
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

        # Avoid symlink loops: track inodes
        if not follow_symlinks:
            try:
                st = os.stat(dirpath)
                key = (st.st_dev, st.st_ino)
                if key in visited_inodes:
                    dirnames[:] = []
                    continue
                visited_inodes.add(key)
            except OSError:
                pass

        for fname in filenames:
            fpath = Path(dirpath) / fname
            if not follow_symlinks and fpath.is_symlink():
                continue
            try:
                sz = fpath.stat().st_size
                if sz >= threshold_bytes:
                    large.append({"path": str(fpath), "size": sz, "name": fname})
            except (PermissionError, OSError, FileNotFoundError):
                continue

    large.sort(key=lambda x: x["size"], reverse=True)  # type: ignore
    return large[:limit]


def search_files(
    root: Path,
    query: str,
    exclude_dirs: set[str] | None = None,
    by_extension: bool = False,
    limit: int = 100,
) -> list[dict[str, object]]:
    exclude_dirs = exclude_dirs or set()
    results: list[dict[str, object]] = []
    q = query.lower()
    if by_extension and not q.startswith("."):
        q = "." + q

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fname in filenames:
            match = False
            if by_extension:
                if fname.lower().endswith(q):
                    match = True
            else:
                if q in fname.lower():
                    match = True
            if match:
                fpath = Path(dirpath) / fname
                try:
                    sz = fpath.stat().st_size
                except OSError:
                    sz = 0
                results.append({"path": str(fpath), "name": fname, "size": sz})
                if len(results) >= limit:
                    return results
        # Also check dir names for query
        if not by_extension:
            for d in list(dirnames):
                if q in d.lower():
                    results.append(
                        {"path": str(Path(dirpath) / d), "name": d, "size": 0, "is_dir": True}
                    )
                    if len(results) >= limit:
                        return results
    return results


def directory_size(root: Path, exclude_dirs: set[str] | None = None) -> dict[str, object]:
    exclude_dirs = exclude_dirs or set()
    total_size = 0
    file_count = 0
    dir_count = 0
    largest: list[dict[str, object]] = []

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        dir_count += 1
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.is_symlink():
                continue
            try:
                sz = fpath.stat().st_size
                total_size += sz
                file_count += 1
                # track largest
                largest.append({"path": str(fpath), "size": sz})
            except (PermissionError, OSError, FileNotFoundError):
                continue

    largest.sort(key=lambda x: x["size"], reverse=True)  # type: ignore
    breakdown: list[dict[str, object]] = []
    # Also collect immediate children sizes
    try:
        for child in root.iterdir():
            if child.name in exclude_dirs:
                continue
            if child.is_symlink():
                continue
            try:
                if child.is_file():
                    breakdown.append(
                        {
                            "name": child.name,
                            "path": str(child),
                            "size": child.stat().st_size,
                            "is_dir": False,
                        }
                    )
                elif child.is_dir():
                    c_size = 0
                    for _, _, files in os.walk(child, followlinks=False):
                        for f in files:
                            with contextlib.suppress(OSError):
                                c_size += (Path(child) / f).stat().st_size
                    # quick approx: walk again? simpler: sum via os.walk limited
                    # Actually do proper
                    c_size2 = 0
                    for dirpath, dirnames2, filenames2 in os.walk(child, followlinks=False):
                        dirnames2[:] = [d for d in dirnames2 if d not in exclude_dirs]
                        for fn in filenames2:
                            with contextlib.suppress(OSError):
                                c_size2 += (Path(dirpath) / fn).stat().st_size
                    breakdown.append(
                        {"name": child.name, "path": str(child), "size": c_size2, "is_dir": True}
                    )
            except (PermissionError, OSError):
                continue
        breakdown.sort(key=lambda x: x["size"], reverse=True)  # type: ignore
    except PermissionError:
        pass

    return {
        "path": str(root),
        "total_size": total_size,
        "file_count": file_count,
        "dir_count": dir_count,
        "largest_files": largest[:10],
        "breakdown": breakdown[:20],
    }


def find_empty_dirs(root: Path, exclude_dirs: set[str] | None = None) -> list[str]:
    exclude_dirs = exclude_dirs or set()
    empty: list[str] = []
    for dirpath, dirnames, _filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        # Check if dir is empty (no files and no subdirs after exclusion would be visited but we count actual)
        try:
            # A dir is empty if it has no files and all subdirs are also empty? Simple: no files and no subdirs in filesystem listing that are not excluded
            entries = list(Path(dirpath).iterdir())
            # filter excluded
            filtered = [e for e in entries if e.name not in exclude_dirs]
            if not filtered:
                empty.append(dirpath)
            elif all(e.is_dir() for e in filtered):
                # Check if all subdirs are traversable; we will detect them separately, but for leaf empty detection we already have leaf case
                pass
        except (PermissionError, OSError):
            continue
    # Deduplicate leaf-only: keep those that actually have zero files recursively? simpler: keep dirs that contain zero files (not just immediate)
    # Re-evaluate: count files recursively
    truly_empty: list[str] = []
    for d in empty:
        try:
            # If top-level empty, it's already empty
            # But we want to include only dirs that have no files at all (not just immediate children empty because subdirs exist)
            # os.walk already visits all; empty dirs are those with no files and no subdirs -> leaf empty dirs
            # That's the desired simple definition
            truly_empty.append(d)
        except Exception:
            continue
    return truly_empty


def find_duplicates(
    root: Path,
    exclude_dirs: set[str] | None = None,
    min_size: int = 1,
    limit_groups: int = 20,
) -> list[dict[str, object]]:
    exclude_dirs = exclude_dirs or set()
    # First group by size
    size_map: dict[int, list[Path]] = {}
    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        for fname in filenames:
            fpath = Path(dirpath) / fname
            if fpath.is_symlink():
                continue
            try:
                sz = fpath.stat().st_size
                if sz < min_size:
                    continue
                size_map.setdefault(sz, []).append(fpath)
            except (PermissionError, OSError, FileNotFoundError):
                continue

    # For groups with same size, hash
    duplicates: list[dict[str, object]] = []
    for size, paths in size_map.items():
        if len(paths) < 2:
            continue
        # Hash files (use partial hash for large files optimization: first chunk + size already grouped, then full)
        hash_map: dict[str, list[str]] = {}
        for p in paths:
            try:
                h = file_hash(p)
                hash_map.setdefault(h, []).append(str(p))
            except (PermissionError, OSError, FileNotFoundError):
                continue
        for h, group in hash_map.items():
            if len(group) > 1:
                duplicates.append({"hash": h, "size": size, "files": group, "count": len(group)})

    duplicates.sort(key=lambda x: x["size"], reverse=True)  # type: ignore
    return duplicates[:limit_groups]


def file_hash(path: Path, chunk_size: int = 8192) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()
