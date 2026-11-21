"""Opt-in SQLite history helper; the CLI does not record commands automatically.

Callers must avoid recording command lines containing credentials or other secrets.
"""

import os
import sqlite3
from contextlib import closing
from pathlib import Path

from forgekit.constants import DEFAULT_HISTORY_FILE


def get_db(path: Path | None = None) -> sqlite3.Connection:
    p = path or DEFAULT_HISTORY_FILE
    p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if p.is_symlink():
        raise OSError(f"Refusing symbolic-link history database: {p}")
    if not p.exists():
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(p, flags, 0o600)
        os.close(fd)
    conn = sqlite3.connect(str(p))
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                exit_code INTEGER,
                duration_ms INTEGER
            )"""
        )
        conn.commit()
    except Exception:
        conn.close()
        raise
    return conn


def record(
    command: str, exit_code: int = 0, duration_ms: int | None = None, path: Path | None = None
) -> None:
    with closing(get_db(path)) as conn, conn:
        conn.execute(
            "INSERT INTO history (command, exit_code, duration_ms) VALUES (?, ?, ?)",
            (command, exit_code, duration_ms),
        )
