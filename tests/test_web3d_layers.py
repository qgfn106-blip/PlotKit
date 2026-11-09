"""浏览器 3D 图层（volume / particles）的二进制出口。"""

from __future__ import annotations

import json
import struct

import numpy as np
import pytest

import plotkit as pk
from plotkit.server.app import create_app

MAGIC = b"PK01"


def _has_pyvista() -> bool:
    try:
        __import__("pyvista")
        return True
    except Exception:  # noqa: BLE001 - 未安装可选依赖
        return False


requires_pyvista = pytest.mark.skipif(not _has_pyvista(), reason="未安装 pyvista")


def _grid_figure(n: int = 16) -> pk.Figure:
    xv = np.linspace(-1.0, 1.0, n)
    yv = np.linspace(-1.0, 1.0, n)
    zv = np.linspace(-1.0, 1.0, n)
    X, Y, Z = np.meshgrid(xv, yv, zv, indexing="ij")
    blob = np.exp(-(X**2 + Y**2 + Z**2) / 0.25)
    field = np.transpose(blob, (2, 1, 0)).copy()  # (nz, ny, nx)，x 变化最快
    figure = pk.figure()
    figure.add_data("x", xv)
    figure.add_data("y", yv)
    figure.add_data("z", zv)
    figure.add_data("f", field, role="field")
    figure.add("volume", {"x": "x", "y": "y", "z": "z", "values": "f"})
    return figure


def _client(figure):
    from fastapi.testclient import TestClient

    return TestClient(create_app(figure))


def test_volume_field_frame_layout():
    client = _client(_grid_figure())
    res = client.get(
        "/api/volume", params={"x": "x", "y": "y", "z": "z", "values": "f"}
    )
    assert res.status_code == 200
    body = res.content
    assert body[:4] == MAGIC
    mlen, count = struct.unpack("<II", body[4:12])
    meta = json.loads(body[12 : 12 + mlen])
    assert meta["nx"] == meta["ny"] == meta["nz"] == 16
    vals = np.frombuffer(body[12 + mlen :], dtype="<f4")
    assert vals.size == count == 16**3
    assert vals.max() > 0.9  # 偶数网格不落原点，峰值略小于 1


@requires_pyvista
def test_volume_surface_returns_mesh():
    client = _client(_grid_figure())
    res = client.get(
        "/api/volume",
        params={
            "x": "x",
            "y": "y",
            "z": "z",
            "values": "f",
            "mode": "surface",
            "level": 0.3,
        },
    )
    assert res.status_code == 200
    body = res.content
    assert body[:4] == MAGIC
    mlen, nvert, ntri = struct.unpack("<III", body[4:16])
    assert nvert > 20 and ntri > 20
    pos = np.frombuffer(body[16 + mlen : 16 + mlen + nvert * 12], dtype="<f4").reshape(
        -1, 3
    )
    assert np.isfinite(pos).all()
    assert np.abs(pos).max() < 1.01  # 顶点在数据包围盒内
    idx = np.frombuffer(body[16 + mlen + nvert * 24 :], dtype="<u4")
    assert idx.size == ntri * 3 and idx.max() < nvert


def test_volume_surface_rejects_empty_level():
    client = _client(_grid_figure())
    res = client.get(
        "/api/volume",
        params={
            "x": "x",
            "y": "y",
            "z": "z",
            "values": "f",
            "mode": "surface",
            "level": 5.0,
        },
    )
    assert res.status_code == 400


def test_particles_frame_layout():
    n = 500
    t = np.linspace(0.0, 1.0, n)
    figure = pk.figure()
    figure.add_data("x", np.cos(6.0 * t))
    figure.add_data("y", np.sin(6.0 * t))
    figure.add_data("z", t)
    figure.add_data("c", t)
    figure.add("particles", {"x": "x", "y": "y", "z": "z", "c": "c"})
    res = _client(figure).get(
        "/api/particles",
        params={
            "x": "x",
            "y": "y",
            "z": "z",
            "c": "c",
        },
    )
    assert res.status_code == 200
    body = res.content
    assert body[:4] == MAGIC
    mlen, count = struct.unpack("<II", body[4:12])
    meta = json.loads(body[12 : 12 + mlen])
    assert count == n
    xyz = np.frombuffer(body[12 + mlen : 12 + mlen + n * 12], dtype="<f4").reshape(
        -1, 3
    )
    scal = np.frombuffer(body[12 + mlen + n * 12 :], dtype="<f4")
    assert xyz.shape == (n, 3) and scal.size == n
    assert meta["cmin"] == pytest.approx(0.0) and meta["cmax"] == pytest.approx(1.0)


def test_unknown_dataset_is_404():
    client = _client(_grid_figure())
    res = client.get(
        "/api/volume", params={"x": "nope", "y": "y", "z": "z", "values": "f"}
    )
    assert res.status_code == 404
