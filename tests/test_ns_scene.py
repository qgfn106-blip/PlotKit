"""NS 场 → 普通 PlotKit Figure（D39 三维 spec 图层）。"""

from __future__ import annotations

import numpy as np
import pytest

import plotkit as pk


def test_scene_figure_has_volume_and_particles():
    fig = pk.ns.scene.figure(t=0.05, n=12, particles=300)
    kinds = [layer["kind"] for layer in fig.spec["layers"]]
    assert kinds[:2] == ["volume", "particles"]
    assert "segments" in kinds  # 阶段 4：默认带流线
    assert set(kinds) <= set(pk.kinds())


def test_scene_volume_field_is_regular_grid():
    fig = pk.ns.scene.figure(t=0.05, n=10, particles=100)
    xs = np.asarray(fig.store.values("vx"))
    zs = np.asarray(fig.store.values("vz"))
    field = np.asarray(fig.store.values("speed"))
    assert xs.size == zs.size == 10
    assert field.shape == (10, 10, 10)  # (nz, ny, nx)
    assert np.isfinite(field).all() and field.max() > 0


def test_scene_field_grows_as_tau_shrinks():
    """该解在 t→1 时速度发散：同一个网格上 t 越大峰值越大。"""
    early = np.asarray(
        pk.ns.scene.figure(t=0.2, n=10, particles=50).store.values("speed")
    ).max()
    late = np.asarray(
        pk.ns.scene.figure(t=0.9, n=10, particles=50).store.values("speed")
    ).max()
    assert late > early * 2


def test_scene_accepts_physical_params():
    from plotkit.ns.field import PhysicalParams

    weak = pk.ns.scene.figure(
        t=0.3, n=10, particles=50, physical=PhysicalParams(gamma=2.0)
    )
    strong = pk.ns.scene.figure(
        t=0.3, n=10, particles=50, physical=PhysicalParams(gamma=8.0)
    )
    a = np.asarray(weak.store.values("speed")).max()
    b = np.asarray(strong.store.values("speed")).max()
    assert b == pytest.approx(a * 4.0, rel=0.05)


def test_scene_renders_with_pyvista():
    pytest.importorskip("pyvista")
    fig = pk.ns.scene.figure(t=0.2, n=10, particles=100)
    result = fig.render_result(width=320, height=240, backend="pyvista")
    assert result.payload[:8] == b"\x89PNG\r\n\x1a\n"


def test_scene_has_segments_layer():
    """R4-3：默认场景要带流线（segments）图层，且端点是点对。"""
    from plotkit.ns.scene import figure

    fig = figure(t=0.05, n=20, particles=500, streamlines=6)
    kinds = [layer["kind"] for layer in fig.spec["layers"]]
    assert kinds == ["volume", "particles", "segments"]
    sx = fig.store.values("sx")
    assert sx.size % 2 == 0 and sx.size > 0


def test_streamlines_stay_inside_box():
    from plotkit.ns import field as ns_field
    from plotkit.ns.scene import streamline_segments

    f = ns_field.SimilarityField(ns_field.SimilarityParams())
    sx, sy, sz = streamline_segments(
        f, 0.05, seeds=4, steps=20, extent=0.4, z_extent=0.9
    )
    assert sx.size == sy.size == sz.size
    assert np.all(np.isfinite(sx)) and np.all(np.isfinite(sz))
    assert np.max(np.hypot(sx, sy)) <= 0.4 * 1.16
    assert np.max(np.abs(sz)) <= 0.9 * 1.26


def test_segments_endpoint_serves_pairs():
    from fastapi.testclient import TestClient

    from plotkit.server.app import create_app

    fig = pk.figure()
    xs = np.array([0.0, 1.0, 0.0, 1.0])
    ys = np.array([0.0, 1.0, 1.0, 0.0])
    zs = np.array([0.0, 0.0, 1.0, 1.0])
    for name, values in (("sx", xs), ("sy", ys), ("sz", zs)):
        fig.add_data(name, values)
    fig.add("segments", {"x": "sx", "y": "sy", "z": "sz"})
    client = TestClient(create_app(fig))
    res = client.get("/api/segments", params={"x": "sx", "y": "sy", "z": "sz"})
    assert res.status_code == 200
    body = res.content
    assert body[:4] == b"PK01"
    meta_len = int.from_bytes(body[4:8], "little")
    assert int.from_bytes(body[8:12], "little") == 4  # 4 个端点 = 2 段
    assert meta_len > 0
    assert (
        client.get(
            "/api/segments", params={"x": "nope", "y": "sy", "z": "sz"}
        ).status_code
        == 404
    )
