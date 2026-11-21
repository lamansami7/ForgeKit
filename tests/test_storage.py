"""Optional storage helpers use isolated paths and never hide write errors."""

import os
import stat

import pytest

from forgekit.storage import cache, history


def test_cache_keys_do_not_collide_or_escape_and_clear_only_own_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "DEFAULT_CACHE_DIR", tmp_path)
    assert cache.cache_path("a/b") != cache.cache_path("a?b")
    assert cache.cache_path("../../other").parent == tmp_path
    (tmp_path / "unrelated.json").write_text("keep")
    cache.set("a/b", {"value": 1})
    cache.set("a?b", {"value": 2})
    assert cache.get("a/b") == {"value": 1}
    assert cache.get("a?b") == {"value": 2}
    assert cache.clear() == 2
    assert (tmp_path / "unrelated.json").read_text() == "keep"


def test_cache_write_failure_does_not_replace_previous_entry(tmp_path, monkeypatch):
    monkeypatch.setattr(cache, "DEFAULT_CACHE_DIR", tmp_path)
    cache.set("key", {"valid": True})
    with pytest.raises(TypeError):
        cache.set("key", object())
    assert cache.get("key") == {"valid": True}
    assert not list(tmp_path.glob("*.tmp"))


def test_cache_reports_corrupt_entry(tmp_path, monkeypatch, caplog):
    monkeypatch.setattr(cache, "DEFAULT_CACHE_DIR", tmp_path)
    cache.cache_path("key").write_text("not json")
    assert cache.get("key") is None
    assert "Cannot read cache entry" in caplog.text


def test_history_records_in_temporary_database_and_uses_private_mode(tmp_path):
    db = tmp_path / "history.db"
    history.record("system memory", exit_code=0, duration_ms=12, path=db)
    conn = history.get_db(db)
    try:
        row = conn.execute("SELECT command, exit_code, duration_ms FROM history").fetchone()
    finally:
        conn.close()
    assert row == ("system memory", 0, 12)
    if os.name == "posix":
        assert stat.S_IMODE(db.stat().st_mode) == 0o600


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_history_refuses_symlink(tmp_path):
    target = tmp_path / "target"
    target.write_text("untouched")
    link = tmp_path / "history.db"
    link.symlink_to(target)
    with pytest.raises(OSError, match="symbolic-link"):
        history.record("test", path=link)
    assert target.read_text() == "untouched"
