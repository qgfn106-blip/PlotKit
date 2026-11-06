"""构图缓存与压缩：同一份 spec 第二次请求必须命中缓存，改 spec 后必须失效。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import plotkit as pk
from plotkit.server.app import create_app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    fig = pk.figure()
    fig.add_plot(x=[0, 1, 2], y=[1, 2, 3], label="a")
    return TestClient(create_app(fig, layout_path=tmp_path / "layout.json"))
