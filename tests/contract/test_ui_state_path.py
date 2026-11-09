"""UI 状态路径契约（X3）：默认路径绝不等于 cwd/layout.json，且与 cwd 无关。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plotkit.ui_state import (
    default_ui_state_path,
    legacy_cwd_layout_path,
    migrate_legacy_layout,
    resolve_ui_state_path,
)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """把 XDG_CONFIG_HOME 与 Path.home 全部钉在 tmp_path 内，绝不写真实用户目录。"""
    config_root = tmp_path / "config"
    fake_home = tmp_path / "home"
    config_root.mkdir()
    fake_home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_root))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    return config_root, fake_home


def test_default_path_never_equals_cwd_layout(sandbox, tmp_path, monkeypatch):
    config_root, fake_home = sandbox
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    default = default_ui_state_path()
    assert default.name == "ui.json"
    assert default.parent.name == "plotkit"
    assert default.resolve() != legacy_cwd_layout_path().resolve()
    assert default.resolve() != (Path.cwd() / "layout.json").resolve()
    assert str(config_root) in str(default)

    # 去掉 XDG_CONFIG_HOME 后走 Path.home()/.config 分支，仍不能落到 cwd
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    from_home = default_ui_state_path()
    assert from_home.name == "ui.json"
    assert str(fake_home) in str(from_home)
    assert from_home.resolve() != legacy_cwd_layout_path().resolve()
    assert from_home.resolve() != (Path.cwd() / "layout.json").resolve()


def test_migrated_state_is_cwd_independent(sandbox, tmp_path, monkeypatch):
    config_root, _ = sandbox
    cwd_a = tmp_path / "cwdA"
    cwd_b = tmp_path / "cwdB"
    cwd_a.mkdir()
    cwd_b.mkdir()
    payload = {"panel": "left", "zoom": 3, "theme": "netlab-dark"}
    (cwd_a / "layout.json").write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )

    monkeypatch.chdir(cwd_a)
    target = default_ui_state_path()
    assert migrate_legacy_layout(target) is True
    assert target.is_file()
    assert target.resolve() != legacy_cwd_layout_path().resolve()

    monkeypatch.chdir(cwd_b)
    assert default_ui_state_path() == target
    assert not (cwd_b / "layout.json").exists()
    with target.open("r", encoding="utf-8") as handle:
        assert json.load(handle) == payload
    # 已存在 / B 目录没有 legacy 文件，重复迁移不得覆盖
    assert migrate_legacy_layout(target) is False
    assert json.loads(resolve_ui_state_path().read_text(encoding="utf-8")) == payload


def test_explicit_path_wins(sandbox, tmp_path):
    config_root, _ = sandbox
    explicit = tmp_path / "explicit" / "ui.json"
    assert resolve_ui_state_path(explicit) == explicit
    assert resolve_ui_state_path(str(explicit)) == explicit
    assert (
        resolve_ui_state_path(explicit).resolve() != default_ui_state_path().resolve()
    )
    assert str(config_root) in str(default_ui_state_path())
