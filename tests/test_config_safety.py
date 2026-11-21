"""Configuration safety, validation, and effective CLI defaults."""

import json
import os
import stat
import tomllib

import pytest
from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.config import ForgeConfig, default_config_file
from forgekit.exceptions import ConfigError

runner = CliRunner()


def test_invalid_toml_is_not_silently_replaced(tmp_path):
    path = tmp_path / "broken.toml"
    original = "[general\ncolors = true\n"
    path.write_text(original)
    validation = runner.invoke(app, ["config", "validate", "--path", str(path), "--json"])
    assert validation.exit_code == 1
    assert json.loads(validation.output)["valid"] is False
    update = runner.invoke(
        app, ["config", "set", "general.colors", "false", "--path", str(path), "--json"]
    )
    assert update.exit_code == 1
    assert "error" in json.loads(update.output)
    assert path.read_text() == original
    doctor = runner.invoke(app, ["--config", str(path), "doctor", "--json"])
    assert doctor.exit_code == 1
    assert any(
        check["name"] == "Configuration" and check["status"] == "fail"
        for check in json.loads(doctor.output)
    )


@pytest.mark.parametrize(
    "data",
    [
        {"mystery": {"x": 1}},
        {"general": {"unknown": True}},
        {"general": {"colors": "false"}},
        {"network": {"http_timeout": True}},
        {"dashboard": {"refresh_interval": "fast"}},
        {"files": {"exclude_dirs": "foo"}},
    ],
)
def test_rejects_unknown_sections_keys_and_wrong_types(data):
    with pytest.raises(ConfigError):
        ForgeConfig.from_dict(data)


def test_set_preserves_comments_strings_and_rejects_unknown_keys(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text('# user comment\n[backup]\ndefault_destination = "/tmp/old" # keep me\n')
    result = runner.invoke(
        app,
        ["config", "set", "backup.default_destination", 'C:\\temp\\"quoted"', "--path", str(path)],
    )
    assert result.exit_code == 0, result.output
    assert "# user comment" in path.read_text()
    assert "# keep me" in path.read_text()
    assert tomllib.loads(path.read_text())["backup"]["default_destination"] == 'C:\\temp\\"quoted"'
    before = path.read_text()
    result = runner.invoke(
        app, ["config", "set", "backup.unknown", "x", "--path", str(path), "--json"]
    )
    assert result.exit_code == 1
    assert "error" in json.loads(result.output)
    assert path.read_text() == before
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_init_force_actually_replaces_existing_file(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("[general]\ncolors = false\n")
    assert runner.invoke(app, ["config", "init", "--path", str(path)]).exit_code == 1
    assert runner.invoke(app, ["config", "init", "--path", str(path), "--force"]).exit_code == 0
    assert tomllib.loads(path.read_text())["general"]["colors"] is True


@pytest.mark.skipif(not hasattr(os, "symlink"), reason="symlinks unavailable")
def test_config_symlink_never_overwritten(tmp_path):
    target = tmp_path / "target"
    target.write_text("do not overwrite")
    link = tmp_path / "config.toml"
    link.symlink_to(target)
    result = runner.invoke(app, ["config", "init", "--path", str(link), "--force", "--json"])
    assert result.exit_code == 1
    assert target.read_text() == "do not overwrite"


def test_xdg_path_and_global_config_are_used(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert default_config_file() == tmp_path / "xdg/forgekit/config.toml"
    config = tmp_path / "custom.toml"
    config.write_text('[files]\nexclude_dirs = ["hidden"]\nlarge_threshold_mb = 0\n')
    tree = tmp_path / "tree"
    (tree / "hidden").mkdir(parents=True)
    (tree / "hidden/ignored").write_text("skip")
    (tree / "visible").write_text("yes")
    result = runner.invoke(app, ["--config", str(config), "--json", "files", "large", str(tree)])
    assert result.exit_code == 0, result.output
    entries = json.loads(result.output)
    assert [item["name"] for item in entries] == ["visible"]
    assert json.loads(
        runner.invoke(app, ["--config", str(config), "--json", "config", "path"]).output
    )["path"] == str(config)


def test_global_json_and_configured_json_are_plain_and_parseable(tmp_path):
    config = tmp_path / "config.toml"
    config.write_text('[general]\noutput_format = "json"\n')
    result = runner.invoke(app, ["--config", str(config), "system", "memory"])
    assert result.exit_code == 0
    assert json.loads(result.output)["total"] > 0
    assert "\x1b[" not in result.output
    result = runner.invoke(app, ["--json", "backup", "verify", str(tmp_path / "missing")])
    assert result.exit_code == 1
    assert "error" in json.loads(result.output)


def test_invalid_numbers_are_rejected_without_modifying_existing_config(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("# keep\n")
    for key, value in [
        ("network.http_timeout", "0"),
        ("dashboard.refresh_interval", "nan"),
        ("files.large_threshold_mb", "-1"),
    ]:
        result = runner.invoke(
            app, ["config", "set", "--path", str(path), "--json", "--", key, value]
        )
        assert result.exit_code == 1
        assert "error" in json.loads(result.output)
        assert path.read_text() == "# keep\n"


def test_unreadable_config_is_reported_not_replaced(tmp_path, monkeypatch):
    from pathlib import Path

    path = tmp_path / "config.toml"
    path.write_text("[general]\ncolors = true\n")
    original = Path.open

    def fake_open(self, *args, **kwargs):
        if self == path:
            raise PermissionError("simulated denial")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", fake_open)
    with pytest.raises(ConfigError, match="simulated denial"):
        ForgeConfig.load(path)
