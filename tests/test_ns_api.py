"""NS 涡旋可视化的 HTTP 接口：二进制帧与诊断双轨。"""

from __future__ import annotations

import json
import struct

import numpy as np
import pytest
from fastapi.testclient import TestClient

from plotkit.contrib.ns.app import create_app as create_ns_app
from plotkit.contrib.ns.field import SimilarityParams, profile_table, velocity_at
from plotkit.server.ns_app import MAGIC


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_ns_app())


def _unframe(body: bytes) -> tuple[dict, np.ndarray]:
    assert body[:4] == MAGIC
    (mlen,) = struct.unpack("<I", body[4:8])
    assert (
        mlen % 4 == 0
    ), "meta 必须 4 字节对齐，否则前端 Float32Array 视图会抛 RangeError"
    meta = json.loads(body[8 : 8 + mlen].decode())
    data = np.frombuffer(body[8 + mlen :], dtype=np.float32)
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
    assert data.size == 32 * 48 * 2  # 每格 (log10 Ω, |u|)
    assert np.isfinite(data).all()


def test_velocity_frame_shapes(client):
    res = client.get("/api/ns/velocity", params={"t": 0.5, "n": 16})
    meta, data = _unframe(res.content)
    assert meta["n"] == 16
    assert data.size == 16**3 * 3  # (u_r, u_θ, u_z)
    assert np.abs(data).max() > 0


def test_velocity_frame_preserves_declared_xyz_order(client):
    n = 16
    extent = 0.35
    z_extent = 1.0
    res = client.get(
        "/api/ns/velocity",
        params={
            "t": 0.5,
            "n": n,
            "extent": extent,
            "z_extent": z_extent,
        },
    )
    meta, data = _unframe(res.content)
    assert meta["order"] == "x fastest, then y, then z; interleaved channels u,v,w"

    # The browser samples idx=(i + j*n + k*n*n)*3 and reads u/v/w
    # interleaved at that point; the server uses the same x-fastest order.
    i, j, k = 11, 4, 10
    points = data.reshape(n**3, 3)
    point = points[i + j * n + k * n * n]
    xs = np.linspace(-extent, extent, n)
    zs = np.linspace(-z_extent, z_extent, n)
    p = SimilarityParams()
    ur, ut, uz = velocity_at(np.hypot(xs[i], xs[j]), zs[k], 0.5, p, profile_table(p))
    theta = np.arctan2(xs[j], xs[i])
    expected = np.array(
        [
            ur * np.cos(theta) - ut * np.sin(theta),
            ur * np.sin(theta) + ut * np.cos(theta),
            uz,
        ]
    )
    np.testing.assert_allclose(point, expected, rtol=2e-5, atol=2e-5)


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
    assert "<path" in svg or "<text" in svg  # mathtext 出的是字形路径或文本


def test_pathlines_are_finite_and_ordered(client):
    res = client.get(
        "/api/ns/pathlines", params={"t0": 0.2, "t1": 0.6, "count": 8, "steps": 16}
    )
    meta, data = _unframe(res.content)
    assert meta["steps"] == 16 and meta["seeds"] >= 8
    assert data.size == meta["steps"] * meta["seeds"] * 3
    assert np.isfinite(data).all()


def test_arrows_returns_structured_glyphs(client):
    """/api/ns/arrows：柱坐标稀疏网格上的位置+速度，供前端 glyph 批量绘制。"""
    res = client.get(
        "/api/ns/arrows", params={"t": 0.4, "n_r": 4, "n_theta": 6, "n_z": 3}
    )
    assert res.status_code == 200
    mlen = int.from_bytes(res.content[4:8], "little")
    meta = json.loads(res.content[8 : 8 + mlen].decode())
    assert meta["count"] == 4 * 6 * 3
    body = res.content[8 + mlen :]
    assert len(body) == meta["count"] * 6 * 4
    assert np.isfinite(np.frombuffer(body, dtype=np.float32)).all()


def test_arrows_rejects_singular_time(client):
    assert client.get("/api/ns/arrows", params={"t": 1.0}).status_code == 400


def _jpeg_data_url(color=(12, 34, 56), size=(24, 16)) -> str:
    import base64
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def test_export_gif_roundtrip(client):
    """前端抓的 canvas 帧 → 服务端合成 GIF。"""
    frames = [_jpeg_data_url((10, 20, 30)), _jpeg_data_url((200, 120, 40))]
    res = client.post(
        "/api/ns/export", json={"frames": frames, "fps": 10, "fmt": "gif"}
    )
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/gif"
    assert res.content[:6] in (b"GIF89a", b"GIF87a")


def test_export_rejects_empty(client):
    assert (
        client.post("/api/ns/export", json={"frames": [], "fmt": "gif"}).status_code
        == 400
    )
