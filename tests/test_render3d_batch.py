"""批量渲染接口（接缝 2）：一次请求 N 帧 → zip。"""

from __future__ import annotations

import io
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient

import plotkit as pk
from plotkit.server.app import create_app


@pytest.fixture()
def client():
    fig = pk.figure()
    x = np.linspace(0, 1, 20)
    fig.add_data("x", x)
    fig.add_data("y", np.sin(x * 6))
    fig.add_plot("line", x="x", y="y")
    return TestClient(create_app(fig)), fig


def _names(body: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(body)) as bundle:
        return bundle.namelist()


def test_batch_returns_ordered_frames(client):
    api, fig = client
    res = api.post("/api/render3d/batch", json={
        "width": 200, "height": 150,
        "frames": [{"spec": fig.spec}, {"spec": fig.spec}, {"spec": fig.spec}],
    })
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    assert res.headers["x-plotkit-frames"] == "3"
    assert _names(res.content) == ["frame_0001.png", "frame_0002.png", "frame_0003.png"]
    with zipfile.ZipFile(io.BytesIO(res.content)) as bundle:
        assert bundle.read("frame_0001.png")[:8] == b"\x89PNG\r\n\x1a\n"


def test_batch_rejects_empty_and_oversized(client):
    api, _ = client
    assert api.post("/api/render3d/batch", json={"frames": []}).status_code == 400
    too_many = [{"spec": {}}] * 601
    assert api.post("/api/render3d/batch", json={"frames": too_many}).status_code == 400


def test_batch_accepts_inline_data(client):
    api, _ = client
    res = api.post("/api/render3d/batch", json={
        "width": 160, "height": 120,
        "data": {"ax": [0, 1, 2], "ay": [0, 1, 0]},
        "frames": [{"spec": {"layers": [{"kind": "line", "data": {"x": "ax", "y": "ay"}}]}}],
    })
    assert res.status_code == 200
    assert _names(res.content) == ["frame_0001.png"]


def test_batch_defaults_to_the_app_figure(client):
    api, _ = client
    res = api.post("/api/render3d/batch", json={"width": 160, "height": 120,
                                                "frames": [{}]})
    assert res.status_code == 200
    assert _names(res.content) == ["frame_0001.png"]


def test_batch_single_frame_endpoint_still_works(client):
    api, _ = client
    assert api.get("/api/render", params={"width": 160, "height": 120}).status_code == 200
