"""NS 场 → 普通 PlotKit Figure（D39 三维 spec 图层）。"""

from __future__ import annotations

import numpy as np
import pytest

import plotkit as pk


def test_scene_figure_has_volume_and_particles():
    fig = pk.ns.scene.figure(t=0.05, n=12, particles=300)
    kinds = [layer["kind"] for layer in fig.spec["layers"]]
    assert kinds == ["volume", "particles"]
    assert set(kinds) <= set(pk.kinds())


def test_scene_volume_field_is_regular_grid():
    fig = pk.ns.scene.figure(t=0.05, n=10, particles=100)
    xs = np.asarray(fig.store.values("vx"))
    zs = np.asarray(fig.store.values("vz"))
    field = np.asarray(fig.store.values("speed"))
    assert xs.size == zs.size == 10
    assert field.shape == (10, 10, 10)          # (nz, ny, nx)
    assert np.isfinite(field).all() and field.max() > 0


def test_scene_field_grows_as_tau_shrinks():
    """该解在 t→1 时速度发散：同一个网格上 t 越大峰值越大。"""
    early = np.asarray(pk.ns.scene.figure(t=0.2, n=10, particles=50).store.values("speed")).max()
    late = np.asarray(pk.ns.scene.figure(t=0.9, n=10, particles=50).store.values("speed")).max()
    assert late > early * 2


def test_scene_accepts_physical_params():
    from plotkit.ns.field import PhysicalParams

    weak = pk.ns.scene.figure(t=0.3, n=10, particles=50,
                              physical=PhysicalParams(gamma=2.0))
    strong = pk.ns.scene.figure(t=0.3, n=10, particles=50,
                                physical=PhysicalParams(gamma=8.0))
    a = np.asarray(weak.store.values("speed")).max()
    b = np.asarray(strong.store.values("speed")).max()
    assert b == pytest.approx(a * 4.0, rel=0.05)


def test_scene_renders_with_pyvista():
    pytest.importorskip("pyvista")
    fig = pk.ns.scene.figure(t=0.2, n=10, particles=100)
    result = fig.render_result(width=320, height=240, backend="pyvista")
    assert result.payload[:8] == b"\x89PNG\r\n\x1a\n"
