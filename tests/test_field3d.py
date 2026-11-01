"""Field3D 通用场景：任意三维流场 → 图层（接缝 1）。"""

from __future__ import annotations

import numpy as np
import pytest

import plotkit as pk


class _Uniform:
    """最简单的场：常数速度、显式包围盒。"""

    bounds = ((-1.0, -1.0, -1.0), (1.0, 1.0, 1.0))
    times = [0.0, 1.0]

    def velocity(self, points, t):  # noqa: ARG002
        pts = np.asarray(points, dtype=float).reshape(-1, 3)
        return np.tile(np.array([1.0, 0.0, 0.0]), (pts.shape[0], 1))


class _Swirl:
    """绕 z 轴的旋转场，用来验证流线确实在转。"""

    bounds = ((-0.5, -0.5, -1.0), (0.5, 0.5, 1.0))

    def velocity(self, points, t):  # noqa: ARG002
        p = np.asarray(points, dtype=float).reshape(-1, 3)
        return np.stack([-p[:, 1], p[:, 0], np.zeros_like(p[:, 2])], axis=1)


class _Broken:
    """退化场：返回 NaN。"""

    def velocity(self, points, t):  # noqa: ARG002
        p = np.asarray(points, dtype=float).reshape(-1, 3)
        return np.full_like(p, np.nan)


class _Tiny:
    """退化场：只有一个点、速度为 0。"""

    bounds = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

    def velocity(self, points, t):  # noqa: ARG002
        return np.zeros((len(np.asarray(points).reshape(-1, 3)), 3))


def test_scene_produces_the_three_layers():
    fig = pk.field3d.scene(_Uniform(), t=0.0, n=12, particles=500, streamlines=4)
    kinds = [layer["kind"] for layer in fig.spec["layers"]]
    assert kinds == ["volume", "particles", "segments"]
    for name in ("vx", "vy", "vz", "speed", "px", "py", "pz", "pc", "sx", "sy", "sz"):
        assert fig.store.values(name).size > 0
    assert fig.store.values("sx").size % 2 == 0   # 端点点对


def test_scene_layers_are_selectable():
    only_particles = pk.field3d.scene(_Uniform(), layers=("particles",), n=8, particles=200)
    assert [l["kind"] for l in only_particles.spec["layers"]] == ["particles"]

    only_volume = pk.field3d.scene(_Uniform(), layers=("volume",), n=8, particles=0)
    assert [l["kind"] for l in only_volume.spec["layers"]] == ["volume"]


def test_scene_uses_field_bounds_by_default():
    fig = pk.field3d.scene(_Uniform(), n=10, particles=100, streamlines=2)
    vx = np.asarray(fig.store.values("vx"))
    assert vx.min() == pytest.approx(-1.0) and vx.max() == pytest.approx(1.0)


def test_scene_survives_degenerate_fields():
    for field in (_Broken(), _Tiny()):
        fig = pk.field3d.scene(field, n=8, particles=100, streamlines=2)
        kinds = [layer["kind"] for layer in fig.spec["layers"]]
        assert "volume" in kinds          # 至少不抛异常，且仍能出图
        assert all(np.all(np.isfinite(np.asarray(fig.store.values(n_))))
                   for n_ in ("vx", "speed"))


def test_swirl_streamlines_turn():
    sx, sy, sz = pk.field3d.streamline_segments(_Swirl(), 0.0, seeds=6, steps=40)
    assert sx.size and sx.size == sy.size == sz.size
    # 绕轴旋转的场：流线端点应当有非零的角位移
    ang = np.arctan2(sy, sx)
    assert np.ptp(ang) > 0.1


def test_array_field_roundtrip(tmp_path):
    x = np.linspace(-1, 1, 7)
    y = np.linspace(-1, 1, 5)
    z = np.linspace(-1, 1, 4)
    grid = np.meshgrid(x, y, z, indexing="ij")
    u = np.ones_like(grid[0]) * 0.5
    v = np.zeros_like(grid[0])
    w = np.zeros_like(grid[0])
    path = tmp_path / "field.npz"
    np.savez(path, t=np.array([0.0, 1.0]), x=x, y=y, z=z,
             u=np.stack([u.transpose(2, 1, 0)] * 2),
             v=np.stack([v.transpose(2, 1, 0)] * 2),
             w=np.stack([w.transpose(2, 1, 0)] * 2))

    field = pk.ns.ArrayField(str(path))
    assert field.bounds[0][0] == pytest.approx(-1.0)
    vel = field.velocity(np.array([[0.3, -0.2, 0.1], [0.0, 0.0, 0.0]]), 0.5)
    assert vel.shape == (2, 3)
    assert np.allclose(vel[:, 0], 0.5) and np.allclose(vel[:, 1:], 0.0)

    fig = pk.field3d.scene(field, n=8, particles=200, streamlines=2)
    assert [layer["kind"] for layer in fig.spec["layers"]] == ["volume", "particles", "segments"]


def test_ns_scene_still_works():
    fig = pk.ns.scene.figure(t=0.05, n=16, particles=300, streamlines=2)
    assert [layer["kind"] for layer in fig.spec["layers"]] == ["volume", "particles", "segments"]
