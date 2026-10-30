"""P13-04：3D 七种（surface / line3d / scatter3d / bar3d / hist3d / quiver3d / stream3d）。"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

import plotkit as pk
from plotkit.backends import mpl_backend


def _colors(payload: bytes) -> int:
    return len(set(Image.open(io.BytesIO(payload)).convert("RGB").getdata()))


def _surface(n: int = 18):
    x = np.linspace(-2, 2, n)
    y = np.linspace(-2, 2, n)
    X, Y = np.meshgrid(x, y)
    return X, Y, np.sin(np.hypot(X, Y))


def _line(n: int = 60):
    t = np.linspace(0, 4 * np.pi, n)
    return np.cos(t), np.sin(t), t / (4 * np.pi)


def _fig(kind: str, cfg: dict) -> pk.Figure:
    fig = pk.figure(size=(5.0, 3.6), theme="netlab-dark")
    fig.add(kind, cfg)
    return fig


def test_surface_renders_with_colorbar():
    X, Y, Z = _surface()
    fig = _fig("surface", {"x": X, "y": Y, "z": Z, "cmap": "viridis"})
    assert _colors(fig.render(width=480, height=340)) > 32
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert hasattr(mpl_fig.axes[0], "get_zlim"), "surface 必须建 3D 轴"


def test_line3d_renders():
    x, y, z = _line()
    assert _colors(_fig("line3d", {"x": x, "y": y, "z": z}).render(width=420, height=300)) > 16


def test_scatter3d_renders_and_colors_by_z():
    rng = np.random.default_rng(3)
    x, y, z = rng.normal(size=80), rng.normal(size=80), rng.normal(size=80)
    fig = _fig("scatter3d", {"x": x, "y": y, "z": z, "cmap": "plasma"})
    assert _colors(fig.render(width=420, height=300)) > 16


def test_bar3d_renders():
    x, y = np.meshgrid(np.arange(4.0), np.arange(4.0))
    z = (x + y).ravel()
    fig = _fig("bar3d", {"x": x.ravel(), "y": y.ravel(), "z": z})
    assert _colors(fig.render(width=420, height=300)) > 16


def test_hist3d_renders():
    rng = np.random.default_rng(5)
    fig = _fig("hist3d", {"x": rng.normal(size=400), "y": rng.normal(size=400), "bins": 8})
    assert _colors(fig.render(width=420, height=300)) > 16


def test_quiver3d_renders():
    n = 5
    g = np.linspace(-1, 1, n)
    X, Y, Z = np.meshgrid(g, g, g)
    fig = _fig("quiver3d", {"x": X, "y": Y, "z": Z, "u": -Y, "v": X, "w": np.zeros_like(Z)})
    assert _colors(fig.render(width=420, height=300)) > 16


def test_stream3d_renders():
    n = 8
    g = np.linspace(-1, 1, n)
    X, Y, Z = np.meshgrid(g, g, g)
    fig = _fig("stream3d", {"x": X, "y": Y, "z": Z, "u": -Y, "v": X, "w": np.zeros_like(Z)})
    assert _colors(fig.render(width=420, height=300)) > 16


def test_3d_kinds_registered():
    from plotkit.backends import registry as reg

    for kind in ("surface", "line3d", "scatter3d", "bar3d", "hist3d", "quiver3d", "stream3d"):
        assert kind in reg.kinds()
        assert reg.resolve(kind).dimension == 3


def test_cannot_mix_2d_and_3d_in_one_subplot():
    X, Y, Z = _surface(8)
    fig = pk.figure()
    fig.add("surface", {"x": X, "y": Y, "z": Z}, subplot=0)
    fig.add("line", {"x": np.arange(5.0), "y": np.arange(5.0)}, subplot=0)
    with pytest.raises(ValueError, match="不能混排"):
        fig.render(width=320, height=240)


def test_view_angles_change_pixels():
    X, Y, Z = _surface()
    fig = _fig("surface", {"x": X, "y": Y, "z": Z})
    a = fig.render(width=400, height=280)
    fig.set_view(0, elev=10, azim=30)
    b = fig.render(width=400, height=280)
    assert a != b, "elev/azim 必须影响渲染"


def test_3d_spec_roundtrip():
    import json

    X, Y, Z = _surface(6)
    fig = _fig("surface", {"x": X, "y": Y, "z": Z})
    fig.set_view(0, elev=25, azim=-40, zlim=(0, 2))
    first = fig.to_json()
    assert pk.Figure(spec=json.loads(first)).to_json() == first


def test_3d_title_and_axis_labels_applied():
    """3D 分支曾提前 return，标题/轴标签全丢（评审发现）。"""
    X, Y, Z = _surface(6)
    fig = _fig("surface", {"x": X, "y": Y, "z": Z})
    fig.set_view(0, title="曲面", xlabel="x 轴", ylabel="y 轴", zlabel="z 轴")
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    ax = mpl_fig.axes[0]
    assert ax.get_title() == "曲面"
    assert ax.get_xlabel() == "x 轴"
    assert ax.get_ylabel() == "y 轴"
    assert ax.get_zlabel() == "z 轴"


def test_surface_rejects_mismatched_xy():
    X, Y, Z = _surface(6)
    fig = _fig("surface", {"x": X, "y": Y, "z": Z[:, :4]})
    with pytest.raises(ValueError, match="形状"):
        fig.render(width=320, height=240)


def test_bar3d_colors_by_height():
    x, y = np.meshgrid(np.arange(4.0), np.arange(4.0))
    z = (x + y).ravel()
    fig = _fig("bar3d", {"x": x.ravel(), "y": y.ravel(), "z": z})
    a = fig.render(width=360, height=260)
    fig.spec["layers"][0]["style"]["color"] = "#ff0000"   # 纯色
    b = fig.render(width=360, height=260)
    assert a != b, "默认应按高度上色，显式 color 才是单色"
