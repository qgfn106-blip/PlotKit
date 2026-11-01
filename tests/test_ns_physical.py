"""物理量旋钮（Γ / a / r_core）与 B 模式等值面·流线的后端测试。

界面暂时还没接上这两组能力，所以这里直接打 API——保证接口本身是对的。
"""

from __future__ import annotations

import numpy as np
import pytest

import plotkit.server.ns_app as ns
from plotkit.ns.app import create_app
from plotkit.ns.field import PhysicalParams, profile_table, velocity_at
from fastapi.testclient import TestClient


def test_physical_mapping_hits_reference_amplitude():
    """默认 Γ=4.26 / a=0.6 / r_core=0.775 应当正好还原之前的调参结果（c∞≈1）。"""
    p = PhysicalParams().to_similarity()
    assert p.x0 == pytest.approx(0.775 ** 2, rel=1e-6)
    assert p.alpha == pytest.approx(0.6)
    assert p.c_inf == pytest.approx(1.0, rel=0.02)


def test_r_core_sets_radial_extent():
    """环量固定在 r=2·r_core 上：核越窄，同半径处 u_θ 越大（环量摊在更小面积上）。"""
    narrow = PhysicalParams(gamma=4.26, r_core=0.3).to_similarity()
    wide = PhysicalParams(gamma=4.26, r_core=1.2).to_similarity()
    r = np.array([[0.25]])
    z = np.array([[0.0]])
    _, ut_n, _ = velocity_at(r, z, 0.5, narrow, profile_table(narrow))
    _, ut_w, _ = velocity_at(r, z, 0.5, wide, profile_table(wide))
    assert float(ut_n[0, 0]) > 5.0 * float(ut_w[0, 0])


def test_gamma_scales_velocity_linearly():
    a = PhysicalParams(gamma=2.0).to_similarity()
    b = PhysicalParams(gamma=8.0).to_similarity()
    r = np.array([[0.2]])
    z = np.array([[0.1]])
    _, ut_a, _ = velocity_at(r, z, 0.5, a, profile_table(a))
    _, ut_b, _ = velocity_at(r, z, 0.5, b, profile_table(b))
    assert float(ut_b[0, 0] / ut_a[0, 0]) == pytest.approx(4.0, rel=0.05)


def test_invalid_physical_params_rejected():
    with pytest.raises(ValueError):
        PhysicalParams(r_core=0.0).to_similarity()
    with pytest.raises(ValueError):
        PhysicalParams(a=-1.0).to_similarity()


def _frame_meta(resp) -> dict:
    """/api/ns/slice 返回二进制帧：magic(4) + meta_len(4) + json。"""
    import json
    import struct

    raw = resp.content
    (mlen,) = struct.unpack("<I", raw[4:8])
    return json.loads(raw[8:8 + mlen].decode("utf-8"))


def test_slice_accepts_phys_and_changes_meta():
    c = TestClient(create_app())
    small = c.get("/api/ns/slice", params={"t": 0.4, "phys": "2,0.6,0.775", "n_r": 32, "n_z": 48})
    big = c.get("/api/ns/slice", params={"t": 0.4, "phys": "8,0.6,0.775", "n_r": 32, "n_z": 48})
    assert small.status_code == 200 and big.status_code == 200
    # Γ 翻 4 倍 → 速度场整体翻 4 倍（环量定义在 r=2·r_core 上，c∞ 线性）
    assert _frame_meta(big)["u_max"] > 3.0 * _frame_meta(small)["u_max"]


def test_phys_parse_error_is_400():
    c = TestClient(create_app())
    assert c.get("/api/ns/slice", params={"phys": "1,2"}).status_code == 400


class _FakeResult:
    params = type("P", (), {"n": 16, "length": 2.0})()

    def __init__(self):
        n = 16
        x, y, z = np.meshgrid(np.linspace(-1, 1, n), np.linspace(-1, 1, n),
                              np.linspace(-1, 1, n), indexing="ij")
        r2 = x * x + y * y
        self.frames = np.stack([
            np.stack([-y, x, np.zeros_like(x)]).reshape(3, n, n, n),
            np.stack([np.zeros_like(x), np.zeros_like(x), np.zeros_like(x)]).reshape(3, n, n, n),
        ])[:1] if False else np.stack([np.stack([-y, x, np.zeros_like(x)]).reshape(3, n, n, n)])
        self.frames = np.repeat(self.frames, 3, axis=0).astype(np.float32)
        self.times = np.array([0.0, 0.5, 1.0])
        self.diag = [{"peak_speed": 1.0, "peak_vorticity": 1.0, "enstrophy": 1.0,
                      "energy": 1.0, "half_peak_radius": 0.5, "divergence": 0.0}] * 3


@pytest.fixture()
def with_fake_solver():
    old = dict(ns._SOLVER)
    ns._SOLVER.update({"result": _FakeResult(), "field": object(), "started": True,
                       "error": None, "progress": 1.0})
    yield ns._SOLVER
    ns._SOLVER.clear()
    ns._SOLVER.update(old)


def test_iso_returns_triangles(with_fake_solver):
    c = TestClient(create_app())
    r = c.get("/api/ns/iso", params={"t": 0.5, "frac": 0.2})
    assert r.status_code == 200
    meta = c.get("/api/ns/iso", params={"t": 0.5, "frac": 0.2}).content
    assert len(meta) > 100


def test_iso_and_streamlines_reject_analytic():
    c = TestClient(create_app())
    assert c.get("/api/ns/iso", params={"t": 0.5, "source": "analytic"}).status_code == 400
    assert c.get("/api/ns/streamlines", params={"t": 0.5, "source": "analytic"}).status_code == 400


def test_streamlines_returns_polylines(with_fake_solver):
    c = TestClient(create_app())
    r = c.get("/api/ns/streamlines", params={"t": 0.5, "seeds": 8, "steps": 40})
    assert r.status_code == 200
    assert len(r.content) > 100
