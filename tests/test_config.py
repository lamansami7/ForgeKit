"""Config tests."""

from typer.testing import CliRunner

from forgekit.cli import app
from forgekit.config import ForgeConfig

runner = CliRunner()


def test_config_show():
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0


def test_config_show_json():
    result = runner.invoke(app, ["config", "show", "--json"])
    assert result.exit_code == 0
    import json

    json.loads(result.output)


def test_config_validate():
    result = runner.invoke(app, ["config", "validate"])
    assert result.exit_code == 0


def test_config_init(tmp_path):
    cfg_path = tmp_path / "test.toml"
    result = runner.invoke(app, ["config", "init", "--path", str(cfg_path)])
    assert result.exit_code == 0
    assert cfg_path.exists()


def test_config_init_no_overwrite(tmp_path):
    cfg_path = tmp_path / "existing.toml"
    cfg_path.write_text('[general]\noutput_format="auto"\n')
    result = runner.invoke(app, ["config", "init", "--path", str(cfg_path)])
    assert result.exit_code != 0
    result2 = runner.invoke(app, ["config", "init", "--path", str(cfg_path), "--force"])
    assert result2.exit_code == 0


def test_config_get():
    result = runner.invoke(app, ["config", "get", "dashboard.refresh_interval"])
    assert result.exit_code == 0


def test_config_set(tmp_path):
    cfg_path = tmp_path / "settest.toml"
    runner.invoke(app, ["config", "init", "--path", str(cfg_path)])
    result = runner.invoke(
        app, ["config", "set", "dashboard.refresh_interval", "3.0", "--path", str(cfg_path)]
    )
    assert result.exit_code == 0
    # Validate
    result2 = runner.invoke(app, ["config", "validate", "--path", str(cfg_path)])
    assert result2.exit_code == 0


def test_config_path():
    result = runner.invoke(app, ["config", "path"])
    assert result.exit_code == 0


def test_config_get_invalid_key():
    result = runner.invoke(app, ["config", "get", "nonexistent.key"])
    assert result.exit_code != 0


def test_config_validation_errors():
    cfg = ForgeConfig()
    cfg.dashboard.refresh_interval = 999
    errors = cfg.validate()
    assert len(errors) >= 1


def test_config_from_dict():
    cfg = ForgeConfig.from_dict({"general": {"output_format": "json"}})
    assert cfg.general.output_format == "json"


def test_config_save_and_load(tmp_path):
    cfg = ForgeConfig()
    cfg.dashboard.refresh_interval = 3.5
    p = tmp_path / "save.toml"
    cfg.save(p)
    loaded = ForgeConfig.load(p)
    assert loaded.dashboard.refresh_interval == 3.5
