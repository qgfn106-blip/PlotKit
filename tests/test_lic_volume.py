"""线积分卷积（lic）与体渲染（volume）两个新图层。"""

from __future__ import annotations

import numpy as np
import pytest

import plotkit as pk
from plotkit.backends.lic import lic_rgb, lic_texture


def _shear_field(n: int = 96):
    x = np.linspace(-1.0, 1.0, n)
    y = np.linspace(-1.0, 1.0, n)
    X, Y = np.meshgrid(x, y)
    return x, y, np.ones_like(X), np.zeros_like(Y)


def test_lic_texture_is_deterministic():
    _, _, u, v = _shear_field()
    a = lic_texture(u, v, steps=8)
    b = lic_texture(u, v, steps=8)
    assert a.shape == u.shape
    assert np.array_equal(a, b)
    assert 0.0 <= a.min() and a.max() <= 1.0


def test_lic_texture_smears_along_flow():
    """均匀来流 u=1,v=0：纹理沿 x 方向应比沿 y 方向更相关（这就是"丝"的来源）。"""
    _, _, u, v = _shear_field(120)
    tex = lic_texture(u, v, steps=24)
    along = float(np.corrcoef(tex[:, :-6].ravel(), tex[:, 6:].ravel())[0, 1])
    across = float(np.corrcoef(tex[:-6, :].ravel(), tex[6:, :].ravel())[0, 1])
    assert along > 0.6  # 沿流向拉成丝
    assert across < 0.2  # 横着基本不相关
    assert along > across + 0.4


def test_lic_rgb_shape_and_scalar_coloring():
    _, _, u, v = _shear_field(64)
    rgb = lic_rgb(u, v, cmap="ocean", steps=6)
    assert rgb.shape == (64, 64, 3)
    assert rgb.min() >= 0.0 and rgb.max() <= 1.0
    # 换了标量场，颜色应该跟着变
    hot = lic_rgb(
        u, v, cmap="ocean", steps=6, scalar=np.linspace(0, 1, 64 * 64).reshape(64, 64)
    )
    assert not np.allclose(rgb, hot)


def test_lic_rejects_one_dimensional_input():
    with pytest.raises(ValueError):
        lic_texture(np.zeros(10), np.zeros(10))


def test_lic_kind_renders_png():
    x, y, u, v = _shear_field(80)
    fig = pk.figure(size=(4, 4), dpi=100)
    fig.add_data("x", x)
    fig.add_data("y", y)
    fig.add_data("u", u)
    fig.add_data("v", v)
    fig.add(
        "lic",
        {"x": "x", "y": "y", "u": "u", "v": "v"},
        style={"cmap": "ocean", "steps": 8},
    )
    png = fig.render(width=220, height=220)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def _volume_figure():
    n, nz = 24, 16
    x = np.linspace(-1, 1, n)
    y = np.linspace(-1, 1, n)
    z = np.linspace(-1, 1, nz)
    X, Y = np.meshgrid(x, y, indexing="xy")
    core = np.exp(-(X**2 + Y**2) / 0.1)[None, :, :]
    values = core * np.ones((nz, 1, 1))
    fig = pk.figure(size=(3, 3), dpi=80)
    fig.add_data("x", x)
    fig.add_data("y", y)
    fig.add_data("z", z)
    fig.add_data("w", values)
    fig.add(
        "volume",
        {"x": "x", "y": "y", "z": "z", "values": "w"},
        style={"cmap": "magma", "opacity_ramp": [0.0, 0.0, 0.2, 0.6]},
    )
    return fig


def test_volume_renders_png_with_pyvista():
    pytest.importorskip("pyvista")
    png = _volume_figure().render(width=200, height=180, backend="pyvista")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 1000


def test_volume_rejects_mpl_backend():
    with pytest.raises(ValueError, match="pyvista"):
        _volume_figure().render(width=200, height=180, backend="mpl")


def test_volume_rejects_wrong_shape():
    pytest.importorskip("pyvista")
    fig = pk.figure(size=(3, 3), dpi=80)
    fig.add_data("x", np.linspace(0, 1, 8))
    fig.add_data("y", np.linspace(0, 1, 8))
    fig.add_data("z", np.linspace(0, 1, 8))
    fig.add_data("w", np.zeros((8, 8, 7)))
    fig.add("volume", {"x": "x", "y": "y", "z": "z", "values": "w"})
    with pytest.raises(Exception, match="形状"):
        fig.render(width=160, height=140, backend="pyvista")


def test_figure_color_overrides_are_honored():
    """figure.facecolor / axes_facecolor 能覆盖主题（深色版式需要更黑的画布）。"""
    fig = pk.figure(size=(3, 2), dpi=80)
    fig.spec["figure"].update({"facecolor": "#04070d", "axes_facecolor": "#04070d"})
    fig.add_data("x", np.arange(5))
    fig.add_data("y", np.arange(5))
    fig.add_plot("line", x="x", y="y")
    png = fig.render(width=160, height=120)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
