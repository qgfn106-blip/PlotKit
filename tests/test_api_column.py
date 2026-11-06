import struct

import numpy as np
import pytest
from fastapi.testclient import TestClient

import plotkit as pk
from plotkit.server.app import create_app


def _decode_field(resp):
    body = resp.content
    assert body[:4] == b"PK01"
    meta_len = struct.unpack("<i", body[4:8])[0]
    n = struct.unpack("<i", body[8:12])[0]
    meta = json.loads(body[12 : 12 + meta_len].decode("utf-8"))
    off = 12 + meta_len
    values = np.frombuffer(body[off : off + n * 4], dtype="<f4")
    return meta, values


import json  # noqa: E402  (放在 helper 之后仅为可读性)


def test_column_endpoint_returns_single_channel():
    fig = pk.figure()
    fig.add_plot("line", x=[0, 1, 2, 3], y=[0, 10, 20, 30], label="ramp")
    client = TestClient(create_app(fig))
    name = fig.layers()[0]["data"]["y"]
    resp = client.get("/api/column", params={"name": name, "pixels": 3})
    assert resp.status_code == 200
    meta, values = _decode_field(resp)
    assert meta["name"] == name
    assert meta["n"] == 3  # 抽稀到 3 点
    assert meta["total"] == 4  # 原始点数仍报告
    assert values[0] == pytest.approx(0.0)
    assert values[-1] == pytest.approx(30.0)  # 保首尾


def test_column_endpoint_keeps_all_points_when_pixels_large():
    fig = pk.figure()
    fig.add_plot("line", x=[0, 1, 2], y=[1, 2, 3], label="small")
    client = TestClient(create_app(fig))
    name = fig.layers()[0]["data"]["y"]
    meta, values = _decode_field(
        client.get("/api/column", params={"name": name, "pixels": 5000})
    )
    assert meta["n"] == 3
    assert values.tolist() == [1.0, 2.0, 3.0]


def test_column_endpoint_unknown_name_is_404():
    fig = pk.figure()
    client = TestClient(create_app(fig))
    resp = client.get("/api/column", params={"name": "nope", "pixels": 10})
    assert resp.status_code == 404
