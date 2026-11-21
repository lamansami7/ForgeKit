"""Optional local cache; the CLI does not write cache entries automatically."""

import hashlib
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from forgekit.constants import DEFAULT_CACHE_DIR

logger = logging.getLogger(__name__)
_PREFIX = "forgekit-cache-"


def cache_path(key: str) -> Path:
    """Hash keys to avoid path traversal, collisions and revealing key contents."""
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return DEFAULT_CACHE_DIR / f"{_PREFIX}{digest}.json"


def get(key: str, max_age_seconds: int = 300) -> Any | None:
    p = cache_path(key)
    try:
        if p.is_symlink():
            raise OSError("refusing symbolic-link cache entry")
        if time.time() - p.stat().st_mtime > max_age_seconds:
            return None
        return json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        logger.warning("Cannot read cache entry %s: %s", p, exc)
        return None


def set(key: str, value: Any) -> None:
    p = cache_path(key)
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{_PREFIX}", suffix=".tmp", dir=p.parent)
    temp = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
        # Replaces the entry itself, not a symlink's target.
        os.replace(temp, p)
    finally:
        temp.unlink(missing_ok=True)


def clear() -> int:
    """Remove only cache files created by this module, never arbitrary JSON."""
    count = 0
    if not DEFAULT_CACHE_DIR.exists():
        return 0
    for entry in DEFAULT_CACHE_DIR.glob(f"{_PREFIX}*.json"):
        digest = entry.name.removeprefix(_PREFIX).removesuffix(".json")
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            continue
        try:
            entry.unlink()
            count += 1
        except OSError as exc:
            logger.warning("Cannot remove cache entry %s: %s", entry, exc)
    return count
