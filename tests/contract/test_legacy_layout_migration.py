"""裁定 ③：X3 默认落点的一次性只读迁移必须真正接线（不是只有函数）。

四条机检：A/B cwd 一致、legacy 存在时首次 GET 返回旧内容、目标已存在时
不覆盖、写入后 cwd 的 legacy 文件字节不变；再加一条「显式 layout_path 不触发
迁移」，保护既有 fixture。全部走 TestClient + 公开 API，沙箱不碰真实 home
或仓库根的 layout.json。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import plotkit as pk
from plotkit.server.app import create_app
from plotkit.ui_state import default_ui_state_path


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    work_a = tmp_path / "work_a"
    work_b = tmp_path / "work_b"
    work_a.mkdir()
    work_b.mkdir()
    config_root = tmp_path / "config"
    fake_home = tmp_path / "home"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_root))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.chdir(work_a)
    return work_a, work_b, default_ui_state_path()


def _write_legacy(path: Path, payload: dict) -> bytes:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    path.write_bytes(raw)
    return raw


def test_default_state_is_cwd_independent_and_imports_legacy(sandbox, monkeypatch):
    work_a, work_b, target = sandbox
    legacy = {"panelWidth": 430, "tabs": ["a", "b"]}
    raw = _write_legacy(work_a / "layout.json", legacy)

    client_a = TestClient(create_app(pk.figure()))
    assert client_a.get("/api/layout").json() == legacy
    assert target.is_file()
    assert (work_a / "layout.json").read_bytes() == raw
    assert not (work_a / "ui.json").exists()

    monkeypatch.chdir(work_b)
    assert not (work_b / "layout.json").exists()
    client_b = TestClient(create_app(pk.figure()))
    assert client_b.get("/api/layout").json() == legacy


def test_existing_target_is_not_overwritten(sandbox):
    work_a, _work_b, target = sandbox
    current = {"panelWidth": 999}
    raw = json.dumps(current, ensure_ascii=False).encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    _write_legacy(work_a / "layout.json", {"legacy": True})

    client = TestClient(create_app(pk.figure()))
    assert client.get("/api/layout").json() == current
    assert target.read_bytes() == raw


def test_put_writes_target_not_cwd_legacy(sandbox):
    work_a, _work_b, _target = sandbox
    legacy = {"old": 1}
    raw = _write_legacy(work_a / "layout.json", legacy)
    client = TestClient(create_app(pk.figure()))
    assert client.get("/api/layout").json() == legacy

    new = {"new": 2}
    put = client.put("/api/layout", json=new)
    assert put.json()["ok"] is True
    assert client.get("/api/layout").json() == new
    assert (work_a / "layout.json").read_bytes() == raw


def test_explicit_layout_path_skips_migration(sandbox):
    work_a, work_b, target = sandbox
    _write_legacy(work_a / "layout.json", {"legacy": True})
    client = TestClient(create_app(pk.figure(), layout_path=work_b / "explicit.json"))
    assert client.get("/api/layout").json() == {}
    assert not target.exists()
