"""`plotkit` 命令行：体检、版本、路径、卸载提示。"""

from __future__ import annotations

import json

from plotkit import cli


def test_doctor_report_shape():
    report = cli.doctor_report()
    assert set(report) >= {"ok", "versions", "requirements", "optional", "problems"}
    assert report["requirements"]["numpy"]["ok"] is True
    assert report["requirements"]["python"]["need"].startswith("3.10")


def test_doctor_command_exit_code():
    assert cli.main(["doctor"]) == 0


def test_doctor_json_is_parseable(capsys):
    assert cli.main(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True


def test_version_command(capsys):
    assert cli.main(["version"]) == 0
    assert "plotkit" in capsys.readouterr().out


def test_where_command_points_at_package(capsys):
    assert cli.main(["where"]) == 0
    assert capsys.readouterr().out.strip().endswith("__init__.py")


def test_cache_dirs_are_under_home():
    from pathlib import Path

    dirs = cli.cache_dirs()
    assert dirs and all(d.parent == Path.home() for d in dirs)


def test_uninstall_without_yes_keeps_dirs(capsys):
    assert cli.main(["uninstall"]) == 0
    out = capsys.readouterr().out
    assert "pip uninstall" in out


def test_main_without_command_prints_help(capsys):
    assert cli.main([]) == 2
    assert "usage" in capsys.readouterr().out.lower()
