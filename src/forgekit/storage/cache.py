"""Simple file cache."""

import contextlib
import json
import time
from pathlib import Path
from typing import Any

from forgekit.constants import DEFAULT_CACHE_DIR


def cache_path(key: str) -> Path:
    safe = "".join(c if c.isalnum() else "_" for c in key)
    return DEFAULT_CACHE_DIR / f"{safe}.json"


def get(key: str, max_age_seconds: int = 300) -> Any | None:
    p = cache_path(key)
    if not p.exists():
        return None
    try:
        if time.time() - p.stat().st_mtime > max_age_seconds:
            return None
        return json.loads(p.read_text())
    except Exception:
        return None


def set(key: str, value: Any) -> None:
    p = cache_path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(Exception):
        p.write_text(json.dumps(value, default=str))


def clear() -> int:
    count = 0
    if not DEFAULT_CACHE_DIR.exists():
        return 0
    for f in DEFAULT_CACHE_DIR.glob("*.json"):
        try:
            f.unlink()
            count += 1
        except OSError:
            pass
    return count
