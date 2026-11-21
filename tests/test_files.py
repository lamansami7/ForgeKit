"""Files tests."""

from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.services.filesystem_service import (
    directory_size,
    find_duplicates,
    find_empty_dirs,
    find_large_files,
    search_files,
)

runner = CliRunner()


def test_find_large_files(tmp_path):
    # Create a file >1MB temporarily but test threshold
    f = tmp_path / "big.bin"
    f.write_bytes(b"0" * 1024 * 100)  # 100KB
    results = find_large_files(tmp_path, threshold_bytes=50 * 1024, limit=10)
    assert any(r["name"] == "big.bin" for r in results)
    results2 = find_large_files(tmp_path, threshold_bytes=200 * 1024, limit=10)
    assert len(results2) == 0


def test_search_files(tmp_path):
    (tmp_path / "hello.txt").write_text("hello")
    (tmp_path / "world.py").write_text("print(1)")
    results = search_files(tmp_path, "hello", limit=10)
    assert len(results) >= 1
    results_ext = search_files(tmp_path, ".py", by_extension=True, limit=10)
    assert any("world.py" in r["name"] for r in results_ext)


def test_directory_size(tmp_path):
    (tmp_path / "a.txt").write_text("hello world")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("hi")
    info = directory_size(tmp_path)
    assert info["file_count"] == 2
    assert info["total_size"] > 0


def test_empty_dirs(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    nonempty = tmp_path / "nonempty"
    nonempty.mkdir()
    (nonempty / "file.txt").write_text("hi")
    empties = find_empty_dirs(tmp_path)
    assert any("empty" in e for e in empties)


def test_duplicates(tmp_path):
    (tmp_path / "a.txt").write_text("same content")
    (tmp_path / "b.txt").write_text("same content")
    (tmp_path / "c.txt").write_text("different")
    dups = find_duplicates(tmp_path)
    assert len(dups) >= 1
    assert any(d["count"] == 2 for d in dups)


def test_cli_large(tmp_path):
    (tmp_path / "x.bin").write_bytes(b"x" * 10240)
    result = runner.invoke(app, ["files", "large", str(tmp_path), "--threshold", "1"])
    assert result.exit_code == 0


def test_cli_search(tmp_path):
    (tmp_path / "testfile.txt").write_text("x")
    result = runner.invoke(app, ["files", "search", str(tmp_path), "testfile"])
    assert result.exit_code == 0


def test_cli_size(tmp_path):
    (tmp_path / "f.txt").write_text("hello")
    result = runner.invoke(app, ["files", "size", str(tmp_path)])
    assert result.exit_code == 0


def test_cli_empty(tmp_path):
    (tmp_path / "empty2").mkdir()
    result = runner.invoke(app, ["files", "empty", str(tmp_path)])
    assert result.exit_code == 0


def test_cli_duplicates(tmp_path):
    (tmp_path / "a.txt").write_text("dup")
    (tmp_path / "b.txt").write_text("dup")
    result = runner.invoke(app, ["files", "duplicates", str(tmp_path)])
    assert result.exit_code == 0


def test_cli_json(tmp_path):
    (tmp_path / "j.txt").write_text("x")
    result = runner.invoke(app, ["files", "size", str(tmp_path), "--json"])
    assert result.exit_code == 0
    import json

    json.loads(result.output)


def test_invalid_path():
    result = runner.invoke(app, ["files", "large", "/nonexistent-path-xyz-123"])
    assert result.exit_code != 0
