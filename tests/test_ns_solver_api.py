"""数值解数据源（模式 B）接到 NS 接口上：source=solver 的契约。

真正的伪谱求解要 15 s，测试里用假场替代，只验证"接口是否真的走了数值解那条路"。
"""

from __future__ import annotations

import json
import struct

import numpy as np
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import plotkit.server.ns_app as ns_api
from plotkit.server.ns_app import MAGIC


class _FakeField:
    """匀速场：u = (0.1, 0.2, 0.3)，便于断言数值确实来自这里而不是解析解。"""

    def velocity(self, points, t):
        pts = np.asarray(points, dtype=float)
        return np.stack([np.full(len(pts), 0.1),
                         np.full(len(pts), 0.2),
                         np.full(len(pts), 0.3)], axis=1)


class _FakeResult:
    times = [0.0, 0.5, 1.0]
    diag = {
        "peak_speed": [0.0, 0.31, 0.62],
        "peak_vorticity": [0.0, 3.1, 6.2],
        "enstrophy": [0.0, 0.11, 0.44],
        "energy": [0.0, 0.05, 0.2],
        "half_peak_radius": [0.0, 0.21, 0.11],
        "divergence": [1e-17, 1e-17, 1e-17],
    }


@pytest.fixture()
def solver_client(monkeypatch):
    monkeypatch.setitem(ns_api._SOLVER, "field", _FakeField())
    monkeypatch.setitem(ns_api._SOLVER, "result", _FakeResult())
    monkeypatch.setitem(ns_api._SOLVER, "progress", 1.0)
    monkeypatch.setitem(ns_api._SOLVER, "error", None)
    app = FastAPI()
    app.include_router(ns_api.router)
    return TestClient(app)


def _unframe(body: bytes):
    assert body[:4] == MAGIC
    (mlen,) = struct.unpack("<I", body[4:8])
    meta = json.loads(body[8:8 + mlen].decode())
    return meta, np.frombuffer(body[8 + mlen:], dtype=np.float32)


def test_meta_lists_both_sources(solver_client):
    meta = solver_client.get("/api/ns/meta").json()
    assert meta["sources"] == ["analytic", "solver"]
    assert meta["solver"]["ready"] is True
    assert "Mode B" in meta["solver"]["label"]


def test_slice_from_solver_field(solver_client):
    res = solver_client.get("/api/ns/slice", params={
        "t": 0.4, "n_r": 32, "n_z": 32, "r_max": 0.3, "z_max": 0.6, "source": "solver",
    })
    assert res.status_code == 200
    meta, data = _unframe(res.content)
    assert meta["source"] == "solver"
    assert "Mode B" in meta["label"]
    # 速度模长 = |(0.1,0.2,0.3)|（假场是常数）
    speed = data[len(data) // 2:]
    assert np.allclose(speed, np.hypot(0.1, np.hypot(0.2, 0.3)), rtol=1e-5)


def test_diagnostics_from_solver_has_single_column(solver_client):
    body = solver_client.get("/api/ns/diagnostics", params={"t": 0.5, "source": "solver"}).json()
    assert body["source"] == "solver"
    assert body["grid"] is None                       # 数值解没有"网格列"这回事
    assert body["analytic"]["omega_max"] == pytest.approx(3.1)
    assert body["analytic"]["n_grid"] == 32


def test_arrows_from_solver_field(solver_client):
    res = solver_client.get("/api/ns/arrows", params={
        "t": 0.2, "n_r": 3, "n_theta": 6, "n_z": 3, "source": "solver",
    })
    assert res.status_code == 200
    meta, data = _unframe(res.content)
    n = meta["count"]
    assert n == 3 * 6 * 3
    vx, vy, vz = data[n * 3:n * 4], data[n * 4:n * 5], data[n * 5:n * 6]
    # 假场给的是柱坐标 (u_r,u_θ,u_z)=(0.1,0.2,0.3)；首个顶点 θ=0 → 笛卡尔 (0.1,0.2,0.3)
    assert np.allclose(vx[0], 0.1, atol=1e-6)
    assert np.allclose(vy[0], 0.2, atol=1e-6)
    assert np.allclose(vz[0], 0.3, atol=1e-6)


def test_solver_not_ready_returns_503(monkeypatch):
    monkeypatch.setitem(ns_api._SOLVER, "field", None)
    monkeypatch.setitem(ns_api._SOLVER, "error", None)
    monkeypatch.setitem(ns_api._SOLVER, "started", True)   # 不再真的启动求解
    app = FastAPI()
    app.include_router(ns_api.router)
    res = TestClient(app).get("/api/ns/slice", params={"t": 0.3, "source": "solver"})
    assert res.status_code == 503
    assert "准备中" in res.json()["detail"]


def test_main_app_can_mount_ns_router():
    import plotkit as pk
    from plotkit.server.app import create_app

    fig = pk.figure()
    fig.add_data("t", np.arange(5.0), role="coord")
    fig.add_data("y", np.arange(5.0), role="series")
    fig.add_plot(x="t", y="y")
    client = TestClient(create_app(fig, with_ns=True))
    assert client.get("/api/ns/meta").status_code == 200
