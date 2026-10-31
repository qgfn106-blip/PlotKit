"""布局（.layout.json）接口测试：GET 空 → PUT → GET 回读，非法输入拒收。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import plotkit as pk
from plotkit.server.app import MAX_LAYOUT_BYTES, create_app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    fig = pk.figure()
    fig.add_plot(x=[0, 1, 2], y=[1, 2, 3])
    return TestClient(create_app(fig, layout_path=tmp_path / "layout.json"))


def test_layout_starts_empty(client: TestClient) -> None:
    res = client.get("/api/layout")
    assert res.status_code == 200
    assert res.json() == {}


def test_layout_roundtrip(client: TestClient, tmp_path: Path) -> None:
    payload = {
        "panelWidth": 430,
        "sections": {"insetgroup": False},
        "expanded": ["labc"],
        "groups": [{"id": "g1", "name": "实验组", "open": True, "layerIds": ["labc"]}],
    }
    put = client.put("/api/layout", json=payload)
    assert put.status_code == 200 and put.json()["ok"] is True
    assert client.get("/api/layout").json() == payload
    # 落盘是原子写，文件必须能独立解析
    on_disk = json.loads((tmp_path / "layout.json").read_text(encoding="utf-8"))
    assert on_disk["groups"][0]["name"] == "实验组"


def test_layout_rejects_non_object(client: TestClient) -> None:
    res = client.put("/api/layout", content=b"[1, 2, 3]")
    assert res.status_code == 400


def test_layout_rejects_broken_json(client: TestClient) -> None:
    res = client.put("/api/layout", content=b"{not json")
    assert res.status_code == 400


def test_layout_rejects_oversize(client: TestClient) -> None:
    blob = b'{"x":"' + b"a" * (MAX_LAYOUT_BYTES + 16) + b'"}'
    res = client.put("/api/layout", content=blob)
    assert res.status_code == 413


def test_layout_survives_restart(client: TestClient, tmp_path: Path) -> None:
    client.put("/api/layout", json={"panelWidth": 500})
    fig = pk.figure()
    fig.add_plot(x=[0, 1], y=[2, 3])
    again = TestClient(create_app(fig, layout_path=tmp_path / "layout.json"))
    assert again.get("/api/layout").json()["panelWidth"] == 500


def test_revision_changes_with_spec_and_store(tmp_path: Path) -> None:
    fig = pk.figure()
    fig.add_plot(x=[0, 1, 2], y=[1, 2, 3])
    first = fig.revision
    assert fig.revision == first, "同状态两次取值必须相同（缓存键要稳定）"
    fig.add_data("extra", [1.0, 2.0], life="append")
    assert fig.revision != first, "数据集变化要换 revision"
    second = fig.revision
    fig.store.push("extra", [3.0])
    assert fig.revision != second, "追加数据要换 revision"
