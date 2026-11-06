"""P13-09：方法级缺口（三角/非结构、3D 补全、信号族）。"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

import plotkit as pk
from plotkit.backends import mpl_backend


def _colors(payload: bytes) -> int:
    return len(set(Image.open(io.BytesIO(payload)).convert("RGB").getdata()))


def _fig(kind: str, cfg: dict) -> pk.Figure:
    fig = pk.figure(size=(5.0, 3.4), theme="netlab-dark")
    fig.add(kind, cfg)
    return fig


def _scatter_xy(n: int = 60, seed: int = 0):
    rng = np.random.default_rng(seed)
    return rng.random(n), rng.random(n)


# ---------------- 三角 / 非结构 ----------------


def test_triplot_renders_triangulation():
    x, y = _scatter_xy()
    fig = _fig("triplot", {"x": x, "y": y})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert mpl_fig.axes[0].lines or mpl_fig.axes[0].collections
    assert _colors(fig.render(width=420, height=280)) > 16


def test_tricontour_and_filled():
    x, y = _scatter_xy(80)
    z = np.sin(6 * x) * np.cos(6 * y)
    assert (
        _colors(
            _fig("tricontour", {"x": x, "y": y, "z": z}).render(width=420, height=280)
        )
        > 16
    )
    assert (
        _colors(
            _fig("tricontourf", {"x": x, "y": y, "z": z}).render(width=420, height=280)
        )
        > 16
    )


def test_tripcolor_renders():
    x, y = _scatter_xy(80)
    z = np.hypot(x, y)
    fig = _fig("tripcolor", {"x": x, "y": y, "z": z})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert mpl_fig.axes[0].collections
    assert _colors(fig.render(width=420, height=280)) > 16


# ---------------- 3D 补全 ----------------


def test_voxels_renders():
    grid = np.zeros((6, 6, 6), dtype=bool)
    grid[1:4, 1:4, 1:4] = True
    fig = _fig("voxels", {"z": grid})
    assert _colors(fig.render(width=420, height=300)) > 16


def test_trisurf_renders():
    x, y = _scatter_xy(50)
    z = np.sin(4 * x) * np.cos(4 * y)
    assert (
        _colors(_fig("trisurf", {"x": x, "y": y, "z": z}).render(width=420, height=300))
        > 16
    )


def test_stem3d_renders():
    x = np.arange(5.0)
    fig = _fig("stem3d", {"x": x, "y": x * 0.5, "z": np.array([0.0, 1, 0, 2, 1])})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert mpl_fig.axes[0].lines
    assert _colors(fig.render(width=420, height=300)) > 16


def test_text3d_places_labels():
    fig = pk.figure(size=(4.6, 3.2))
    fig.add_data("labels", ["甲", "乙"], role="table")
    fig.add(
        "text3d",
        {
            "x": np.array([0.0, 1.0]),
            "y": np.array([0.0, 1.0]),
            "z": np.array([0.0, 1.0]),
            "labels": "labels",
        },
    )
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    texts = [t for t in mpl_fig.axes[0].texts]
    assert len(texts) == 2


# ---------------- 信号族 ----------------


@pytest.mark.parametrize(
    "kind",
    [
        "csd",
        "cohere",
        "acorr",
        "xcorr",
        "angle_spectrum",
        "magnitude_spectrum",
        "phase_spectrum",
    ],
)
def test_signal_kinds_render(kind):
    t = np.linspace(0, 1, 400)
    cfg = {"x": np.sin(2 * np.pi * 20 * t)}
    if kind in ("csd", "cohere", "xcorr"):
        cfg["y"] = np.cos(2 * np.pi * 20 * t) + 0.1 * np.sin(2 * np.pi * 60 * t)
    fig = _fig(kind, cfg)
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert mpl_fig.axes[0].lines
    assert _colors(fig.render(width=420, height=280)) > 16


def test_signal_kinds_require_second_signal_where_needed():
    from plotkit.spec.validate import SpecError

    # 缺 y 在 add 阶段就被拦下（REQUIRED_DATA），不会拖到渲染
    with pytest.raises((ValueError, SpecError), match="y"):
        _fig("csd", {"x": np.arange(10.0)})


def test_new_kinds_registered():
    from plotkit.backends import registry as reg

    for kind in (
        "triplot",
        "tricontour",
        "tricontourf",
        "tripcolor",
        "voxels",
        "trisurf",
        "stem3d",
        "text3d",
        "csd",
        "cohere",
        "acorr",
        "xcorr",
        "angle_spectrum",
        "magnitude_spectrum",
        "phase_spectrum",
    ):
        assert kind in reg.kinds()
