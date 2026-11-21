"""Workspace tests."""

from typer.testing import CliRunner

from forgekit.cli import app

runner = CliRunner()


def test_templates_list():
    result = runner.invoke(app, ["workspace", "templates"])
    assert result.exit_code == 0
    assert "python" in result.output.lower()


def test_templates_json():
    result = runner.invoke(app, ["workspace", "templates", "--json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert "python" in data


def test_create_python(tmp_path):
    result = runner.invoke(
        app, ["workspace", "create", "myproj", "--template", "python", "--path", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert (tmp_path / "myproj" / "README.md").exists()
    assert (tmp_path / "myproj" / "pyproject.toml").exists()


def test_create_node(tmp_path):
    result = runner.invoke(
        app, ["workspace", "create", "nodeproj", "--template", "node", "--path", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert (tmp_path / "nodeproj" / "package.json").exists()


def test_create_generic(tmp_path):
    result = runner.invoke(
        app, ["workspace", "create", "genproj", "--template", "generic", "--path", str(tmp_path)]
    )
    assert result.exit_code == 0
    assert (tmp_path / "genproj" / "README.md").exists()


def test_create_with_git(tmp_path):
    result = runner.invoke(
        app,
        [
            "workspace",
            "create",
            "gitproj",
            "--template",
            "python",
            "--path",
            str(tmp_path),
            "--git",
        ],
    )
    assert result.exit_code == 0
    assert (tmp_path / "gitproj" / ".git").is_dir()


def test_create_invalid_name(tmp_path):
    result = runner.invoke(
        app, ["workspace", "create", "invalid/name", "-t", "python", "--path", str(tmp_path)]
    )
    assert result.exit_code != 0


def test_create_existing_no_force(tmp_path):
    (tmp_path / "existing").mkdir()
    result = runner.invoke(app, ["workspace", "create", "existing", "--path", str(tmp_path)])
    assert result.exit_code != 0


def test_create_existing_with_force(tmp_path):
    proj = tmp_path / "forced"
    proj.mkdir()
    (proj / "README.md").write_text("old")
    result = runner.invoke(
        app,
        [
            "workspace",
            "create",
            "forced",
            "--template",
            "generic",
            "--path",
            str(tmp_path),
            "--force",
        ],
    )
    assert result.exit_code == 0


def test_inspect(tmp_path):
    proj = tmp_path / "inspectme"
    proj.mkdir()
    (proj / "README.md").write_text("# hi")
    result = runner.invoke(app, ["workspace", "inspect", str(proj)])
    assert result.exit_code == 0


def test_inspect_json(tmp_path):
    proj = tmp_path / "inspectjson"
    proj.mkdir()
    (proj / "pyproject.toml").write_text("[project]\nname='test'")
    result = runner.invoke(app, ["workspace", "inspect", str(proj), "--json"])
    assert result.exit_code == 0
    import json

    data = json.loads(result.output)
    assert data["detected_template"] == "python"


def test_unknown_template(tmp_path):
    result = runner.invoke(
        app, ["workspace", "create", "x", "--template", "unknown", "--path", str(tmp_path)]
    )
    assert result.exit_code != 0
