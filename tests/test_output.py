"""Output tests."""

import json

from forgekit.output import print_json, should_use_json


def test_should_use_json():
    assert should_use_json(True) is True
    assert should_use_json(False) is False
    assert should_use_json(False, True) is True


def test_print_json(capsys):
    print_json({"a": 1, "b": 2})
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["a"] == 1
