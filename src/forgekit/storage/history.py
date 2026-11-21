"""History storage (optional SQLite)."""

import sqlite3
from pathlib import Path

from forgekit.constants import DEFAULT_HISTORY_FILE


def get_db(path: Path | None = None) -> sqlite3.Connection:
    p = path or DEFAULT_HISTORY_FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(p))
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
    return conn


def record(
    command: str, exit_code: int = 0, duration_ms: int | None = None, path: Path | None = None
) -> None:
    try:
        conn = get_db(path)
        conn.execute(
            "INSERT INTO history (command, exit_code, duration_ms) VALUES (?, ?, ?)",
            (command, exit_code, duration_ms),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
