"""NS 涡旋可视化的 HTTP 接口：二进制帧与诊断双轨。"""

from __future__ import annotations

import json
import struct

import numpy as np
import pytest
from fastapi.testclient import TestClient

from plotkit.ns.app import create_app as create_ns_app
from plotkit.server.ns_app import MAGIC


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_ns_app())


def _unframe(body: bytes) -> tuple[dict, np.ndarray]:
    assert body[:4] == MAGIC
    (mlen,) = struct.unpack("<I", body[4:8])
    assert mlen % 4 == 0, "meta 必须 4 字节对齐，否则前端 Float32Array 视图会抛 RangeError"
    meta = json.loads(body[8:8 + mlen].decode())
    data = np.frombuffer(body[8 + mlen:], dtype=np.float32)
    return meta, data


def test_meta_reports_mode_and_params(client):
    body = client.get("/api/ns/meta").json()
    assert body["params"]["h"] == pytest.approx(0.005)
    assert body["mode"] == "A-prime"
    assert "not a verified blow-up solution" in body["label"]
    assert len(body["formulas"]) == 4


def test_slice_frame_is_aligned_and_finite(client):
    res = client.get("/api/ns/slice", params={"t": 0.5, "n_r": 32, "n_z": 48})
    assert res.status_code == 200
    meta, data = _unframe(res.content)
    assert meta["n_r"] == 32 and meta["n_z"] == 48
    assert data.size == 32 * 48 * 2          # 每格 (log10 Ω, |u|)
    assert np.isfinite(data).all()


def test_velocity_frame_shapes(client):
    res = client.get("/api/ns/velocity", params={"t": 0.5, "n": 16})
    meta, data = _unframe(res.content)
    assert meta["n"] == 16
    assert data.size == 16 ** 3 * 3          # (u_r, u_θ, u_z)
    assert np.abs(data).max() > 0


def test_diagnostics_has_both_columns(client):
    body = client.get("/api/ns/diagnostics", params={"t": 0.5, "n": 16}).json()
    assert set(body) >= {"analytic", "grid", "label"}
    for key in ("u_max", "omega_max", "enstrophy", "kinetic", "divergence_rel"):
        assert key in body["analytic"]
    # 解析列必须比网格列更接近不可压
    assert body["analytic"]["divergence_rel"] < body["grid"]["divergence_rel"]
    conv = client.get("/api/ns/convergence", params={"t": 0.5}).json()
    assert [int(row["n_grid"]) for row in conv["rows"]] == [32, 64, 96]


def test_formula_svg_is_vector_text(client):
    svg = client.get("/api/ns/formula.svg").content.decode()
    assert svg.lstrip().startswith("<?xml") or svg.lstrip().startswith("<svg")
    assert "<path" in svg or "<text" in svg     # mathtext 出的是字形路径或文本


def test_pathlines_are_finite_and_ordered(client):
    res = client.get("/api/ns/pathlines", params={"t0": 0.2, "t1": 0.6, "count": 8, "steps": 16})
    meta, data = _unframe(res.content)
    assert meta["steps"] == 16 and meta["seeds"] >= 8
    assert data.size == meta["steps"] * meta["seeds"] * 3
    assert np.isfinite(data).all()
