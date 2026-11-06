"""P13-03：矢量场图层（quiver / streamplot）。"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

import plotkit as pk
from plotkit.backends import mpl_backend


def _grid(n: int = 12, m: int = 15):
    x = np.linspace(-2.0, 2.0, m)
    y = np.linspace(-1.5, 1.5, n)
    X, Y = np.meshgrid(x, y)
    U = -Y
    V = X
    return X, Y, U, V


def _colors(payload: bytes) -> int:
    return len(set(Image.open(io.BytesIO(payload)).convert("RGB").getdata()))


def test_quiver_renders_and_draws_arrows():
    X, Y, U, V = _grid()
    fig = pk.figure(size=(5.0, 3.4), theme="netlab-dark")
    fig.add("quiver", {"x": X, "y": Y, "u": U, "v": V})
    payload = fig.render(width=480, height=320)
    assert _colors(payload) > 16
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=100)
    quiver = mpl_fig.axes[0].collections[0]
    assert quiver.get_offsets().shape[0] == X.size


def test_quiver_accepts_flat_vectors():
    """1D 的 x/y/u/v（散点式箭头）也要能画。"""
    fig = pk.figure()
    fig.add(
        "quiver",
        {"x": np.arange(6.0), "y": np.arange(6.0), "u": np.ones(6), "v": np.zeros(6)},
    )
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert mpl_fig.axes[0].collections


def test_quiver_requires_four_keys():
    with pytest.raises(ValueError, match="u"):
        pk.figure().add(
            "quiver", {"x": np.arange(3.0), "y": np.arange(3.0), "v": np.ones(3)}
        )


def test_streamplot_requires_grid():
    """streamplot 必须是二维网格，1D 输入要给可读的报错，而不是 mpl 的底层异常。"""
    fig = pk.figure()
    fig.add(
        "streamplot",
        {"x": np.arange(5.0), "y": np.arange(5.0), "u": np.ones(5), "v": np.ones(5)},
    )
    with pytest.raises(ValueError, match="二维"):
        fig.render(width=320, height=220)


def test_streamplot_renders_on_grid():
    X, Y, U, V = _grid(14, 18)
    fig = pk.figure(size=(5.0, 3.4), theme="netlab-dark")
    fig.add("streamplot", {"x": X, "y": Y, "u": U, "v": V, "density": 1.2})
    payload = fig.render(width=480, height=320)
    assert _colors(payload) > 16


def test_vector_kinds_registered():
    from plotkit.backends import registry as reg

    for kind in ("quiver", "streamplot"):
        assert kind in reg.kinds()
        assert reg.resolve(kind).dimension == 2


def test_quiver_auto_scale_keeps_arrows_readable():
    """自动 scale 必须让中位箭头落在跨度的 2%–15%，否则会糊成一片（2026-10-31 实测过）。"""
    from plotkit.backends.mpl_backend import quiver_scale

    X, Y, U, V = _grid()
    scale = quiver_scale(X, Y, U, V)
    span = float(max(np.ptp(X), np.ptp(Y)))
    median_arrow = float(np.median(np.hypot(U, V))) / scale
    assert 0.02 * span <= median_arrow <= 0.15 * span


def test_quiver_color_by_magnitude():
    """默认按模长上色：改 v 的符号后像素必须变化。"""
    X, Y, U, V = _grid()
    fig = pk.figure(size=(4.2, 3.0))
    fig.add("quiver", {"x": X, "y": Y, "u": U, "v": V})
    a = fig.render(width=360, height=240)
    fig.spec["layers"][0]["style"]["color_by"] = "x"
    b = fig.render(width=360, height=240)
    assert a != b


def test_vector_kinds_spec_roundtrip():
    """四件套①：spec 往返字节相等。"""
    import json

    X, Y, U, V = _grid(6, 7)
    fig = pk.figure()
    fig.add("quiver", {"x": X, "y": Y, "u": U, "v": V, "cmap": "magma"})
    first = fig.to_json()
    assert pk.Figure(spec=json.loads(first)).to_json() == first


def test_vector_kind_rerenders_with_new_xlim():
    """四件套③：改视窗后能重绘（前端缩放走这条路）。"""
    X, Y, U, V = _grid()
    fig = pk.figure(size=(4.4, 3.0))
    fig.add("quiver", {"x": X, "y": Y, "u": U, "v": V})
    base = fig.render(width=380, height=260)
    zoomed = fig.render(width=380, height=260, xlim=(-1.0, 1.0))
    assert zoomed != base


def test_quiver_honours_vmin_vmax():
    X, Y, U, V = _grid()
    fig = pk.figure(size=(4.2, 3.0))
    fig.add("quiver", {"x": X, "y": Y, "u": U, "v": V})
    a = fig.render(width=360, height=240)
    fig.spec["layers"][0]["style"].update({"vmin": 0.0, "vmax": 5.0})
    b = fig.render(width=360, height=240)
    assert a != b, "vmin/vmax 必须影响上色范围"


def test_streamplot_honours_solid_color():
    X, Y, U, V = _grid(14, 18)
    fig = pk.figure(size=(4.2, 3.0))
    fig.add("streamplot", {"x": X, "y": Y, "u": U, "v": V})
    a = fig.render(width=360, height=240)
    fig.spec["layers"][0]["style"]["color"] = "#ff0000"
    b = fig.render(width=360, height=240)
    assert a != b, "纯色流线必须生效"


def test_color_by_rejects_unknown_value():
    X, Y, U, V = _grid(6, 7)
    fig = pk.figure()
    fig.add("quiver", {"x": X, "y": Y, "u": U, "v": V, "color_by": "speed"})
    with pytest.raises(ValueError, match="color_by"):
        fig.render(width=320, height=220)


def test_quiver_key_draws_legend():
    X, Y, U, V = _grid(6, 7)
    fig = pk.figure()
    fig.add("quiver", {"x": X, "y": Y, "u": U, "v": V, "key": True})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert mpl_fig.axes[0].artists, "key=True 应生成 QuiverKey"


def test_barbs_renders():
    X, Y, U, V = _grid(10, 12)
    fig = pk.figure(size=(4.4, 3.0), theme="netlab-dark")
    fig.add("barbs", {"x": X, "y": Y, "u": U, "v": V})
    payload = fig.render(width=420, height=280)
    assert _colors(payload) > 16
