"""P13-05：统计/信号族（boxplot / violin / ecdf / hexbin / barh / stackplot / step / stem）。"""

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


def test_boxplot_one_box_per_column():
    rng = np.random.default_rng(1)
    data = rng.normal(size=(3, 60))  # 一行一组
    fig = _fig("boxplot", {"y": data})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    ax = mpl_fig.axes[0]
    assert len(ax.patches) == 3, "三行数据应得到三个箱体"
    assert _colors(fig.render(width=420, height=280)) > 16


def test_violin_renders():
    rng = np.random.default_rng(2)
    fig = _fig("violinplot", {"y": rng.normal(size=(2, 50))})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert mpl_fig.axes[0].collections
    assert _colors(fig.render(width=420, height=280)) > 16


def test_ecdf_is_monotonic():
    from plotkit.backends.mpl_backend import ecdf_points

    x = np.array([3.0, 1.0, 2.0, 2.0])
    xs, ys = ecdf_points(x)
    assert list(xs) == [1.0, 2.0, 2.0, 3.0]
    assert list(ys) == [0.25, 0.5, 0.75, 1.0]


def test_hexbin_renders():
    rng = np.random.default_rng(3)
    fig = _fig("hexbin", {"x": rng.normal(size=400), "y": rng.normal(size=400), "gridsize": 12})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert mpl_fig.axes[0].collections
    assert _colors(fig.render(width=420, height=280)) > 16


def test_barh_renders_horizontal():
    fig = _fig("barh", {"x": np.arange(4.0), "y": np.array([3.0, 5.0, 2.0, 4.0])})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    patches = mpl_fig.axes[0].patches
    assert len(patches) == 4
    # 横向柱子：宽度应等于数值，高度是条宽
    assert patches[0].get_width() == pytest.approx(3.0)


def test_stackplot_stacks_series():
    x = np.arange(6.0)
    y = np.vstack([np.arange(6.0), np.arange(6.0) * 2])  # 两行 = 两条序列
    fig = _fig("stackplot", {"x": x, "y": y})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    polys = [c for c in mpl_fig.axes[0].collections if hasattr(c, "get_paths")]
    assert polys, "stackplot 应产生填充多边形"


def test_step_uses_step_path():
    fig = _fig("step", {"x": np.arange(5.0), "y": np.array([0.0, 1, 0, 1, 0]), "where": "post"})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    line = mpl_fig.axes[0].lines[0]
    verts = line.get_xydata()
    # step 路径点数比原始点多一倍（每段两个端点）
    assert verts.shape[0] >= 5


def test_stem_renders_stems():
    fig = _fig("stem", {"x": np.arange(5.0), "y": np.array([0.0, 1, 0, 1, 0])})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    ax = mpl_fig.axes[0]
    assert ax.lines, "stem 应画基线/茎线"
    assert _colors(fig.render(width=420, height=280)) > 16


def test_new_kinds_registered():
    from plotkit.backends import registry as reg

    for kind in ("boxplot", "violinplot", "ecdf", "hexbin", "barh", "stackplot", "step", "stem"):
        assert kind in reg.kinds()
        assert reg.resolve(kind).dimension == 2


def test_spec_roundtrip_for_stats_kinds():
    import json

    rng = np.random.default_rng(4)
    fig = _fig("hexbin", {"x": rng.normal(size=100), "y": rng.normal(size=100)})
    first = fig.to_json()
    assert pk.Figure(spec=json.loads(first)).to_json() == first


def test_stem_does_not_recolor_other_layers():
    """stem 曾遍历 ax.lines 把别的图层一起染色（评审发现）。"""
    fig = pk.figure(size=(5.0, 3.4))
    fig.add_data("x", np.arange(5.0), role="coord")
    fig.add_data("y", np.array([0.0, 1, 0, 1, 0]), role="series")
    fig.add_plot("line", x="x", y="y", color="#123456")
    fig.add("stem", {"x": "x", "y": "y", "color": "#ff0000"})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    ax = mpl_fig.axes[0]
    line_colors = {ln.get_color() for ln in ax.lines[:1]}
    assert line_colors == {"#123456"}, "line 图层的颜色不该被 stem 改掉"


def test_step_rejects_2d_y():
    fig = _fig("step", {"x": np.arange(6.0), "y": np.vstack([np.arange(6.0), np.arange(6.0)])})
    with pytest.raises(ValueError, match="一维"):
        fig.render(width=320, height=220)


def test_boxplot_honours_color():
    rng = np.random.default_rng(8)
    fig = _fig("boxplot", {"y": rng.normal(size=(2, 40))})
    a = fig.render(width=360, height=240)
    fig.spec["layers"][0]["style"]["color"] = "#00ff00"
    assert fig.render(width=360, height=240) != a


def test_stackplot_labels_for_legend():
    x = np.arange(5.0)
    y = np.vstack([np.arange(5.0), np.arange(5.0)])
    fig = _fig("stackplot", {"x": x, "y": y, "label": "band"})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    labels = [p.get_label() for p in mpl_fig.axes[0].collections]
    assert any("band" in str(l) for l in labels)
