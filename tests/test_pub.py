"""论文级出图能力（v0.2）：误差棒 / 对数轴 / 刻度 / 字号 / 装饰 / 内嵌子图。

D33 之后渲染只剩 matplotlib 一条路，所以这里直接断言 **mpl 的 artist**，
而不是再去看一份 plotly JSON（那份出口已随 plotly 退役一起删掉）。
"""

from __future__ import annotations

import numpy as np
import pytest

import plotkit as pk
from plotkit.backends import mpl_backend
from plotkit.spec import validate as v


def _paper_figure() -> pk.Figure:
    x = np.linspace(1.4, 10.0, 12)
    y = 0.5 * x**-3.0
    err = 0.08 * y
    fig = pk.figure(size=(5.6, 4.4), dpi=200)
    fig.add_plot(
        "scatter",
        x=x,
        y=y,
        label="β = 3",
        style={"mode": "markers", "width": 0.0},
    )
    fig.add_data("xerr", 0.06 * x, role="series")
    fig.add_data("yerr", err, role="series")
    fig.set_view(
        0,
        xlabel="$R_G$ (μm)",
        ylabel=r"$D_{eff}^{\theta}$ (rad$^2$ s$^{-1}$)",
        xscale="log",
        yscale="log",
        xlim=(1.3, 11.0),
        ylim=(3e-5, 1.4e-1),
        grid=False,
        ticks={"inside": True, "mirror": True, "minor": True},
        loglabels="plain-x",
    )
    fig.layers()[0]["data"].update({"error_x": "xerr", "error_y": "yerr"})
    fig.layers()[0]["style"]["error"] = {"width": 4.0, "thickness": 1.2}
    return fig


def _axes(fig: pk.Figure):
    return mpl_backend.to_figure(fig.spec, fig.store, dpi=100).axes[0]


# ---------------- 误差棒 ----------------


def test_error_bars_are_drawn():
    ax = _axes(_paper_figure())
    # errorbar 的竖线/横线是 LineCollection，落在 ax.collections 里
    assert ax.collections, "误差棒应当作为 collection 画出来"


def test_error_bars_are_not_downsampled_away():
    x = np.linspace(0, 10, 5000)
    y = np.sin(x)
    fig = pk.figure()
    fig.add_data("x", x)
    fig.add_data("y", y)
    fig.add_data("e", np.full_like(x, 0.1))
    fig.add_plot("line", x="x", y="y")
    fig.layers()[0]["data"]["error_y"] = "e"
    ax = _axes(fig)
    # 抽稀会破坏误差数组对齐，所以带误差棒时数据必须原样给
    line = ax.lines[0]
    assert len(line.get_ydata()) == len(y)


def test_asymmetric_error_draws_lower_bar():
    x = np.linspace(0, 1, 5)
    fig = pk.figure()
    fig.add_data("x", x)
    fig.add_data("y", x)
    fig.add_data("up", np.full(5, 0.2))
    fig.add_data("down", np.full(5, 0.05))
    fig.add_plot("scatter", x="x", y="y")
    fig.layers()[0]["data"].update({"error_y": "up", "error_y_minus": "down"})
    ax = _axes(fig)
    assert ax.collections, "上下不对称的误差棒也要画出来"


# ---------------- 对数轴 ----------------


def test_log_axis_keeps_data_space_range():
    fig = _paper_figure()
    ax = _axes(fig)
    assert ax.get_xscale() == "log"
    lo, hi = ax.get_xlim()
    # mpl 的 xlim 是数据值（不是 log10 指数），与 plotly 的语义相反
    assert lo == pytest.approx(1.3, rel=1e-6)
    assert hi == pytest.approx(11.0, rel=1e-6)


def test_log_range_rejects_nonpositive():
    """对数轴出现非正数边界必须在 spec 校验阶段就被挡下（mpl 自己不会报错）。"""
    fig = pk.figure()
    fig.add_plot("line", x=[1, 2], y=[1, 2])
    fig.set_view(0, xscale="log", xlim=(0.0, 5.0))
    report = v.validate_spec(fig.spec)
    assert [i for i in report.errors if i.code == "layer.view.log_limit"]


# ---------------- 刻度与字号 ----------------


def test_ticks_inside_mirror_and_fonts():
    fig = _paper_figure()
    fig.spec["figure"]["fonts"] = {"axis": 15, "tick": 9}
    ax = _axes(fig)
    params = ax.xaxis.get_tick_params()
    assert params["direction"] == "in"
    assert params["top"] is True  # mirror → 上边也画刻度
    assert ax.get_xticklabels()[0].get_fontsize() == pytest.approx(9)
    assert ax.xaxis.label.get_fontsize() == pytest.approx(15)


def test_minor_ticks_toggle():
    fig = pk.figure()
    fig.add_plot("line", x=[1, 2], y=[1, 2])
    fig.set_view(0, xscale="log", ticks={"minor": True})
    assert _axes(fig).xaxis.get_minorticklocs().size > 0
    fig.set_view(0, ticks={"minor": False})
    assert _axes(fig).xaxis.get_minorticklocs().size == 0


# ---------------- 装饰 ----------------


def test_triangle_and_arrow_shapes_are_drawn():
    fig = pk.figure()
    fig.add_plot("scatter", x=[1, 2], y=[1, 2])
    fig.add_shape("triangle", anchor=(1.2, 1.0), decades=0.5, slope=-3, text="−3")
    fig.add_shape("arrow", start=(1.5, 0.5), end=(1.5, 2.0), text="ρ_B")
    ax = _axes(fig)
    assert ax.patches or ax.lines, "三角形/箭头至少要画出图形元素"
    texts = [t.get_text() for t in ax.texts]
    assert any("−3" in t for t in texts)


def test_math_text_renders():
    fig = pk.figure()
    fig.add_plot("line", x=[1, 2], y=[1, 2])
    fig.set_view(0, xlabel="$R_G$")
    ax = _axes(fig)
    # mpl 直接吃 mathtext，标签里保留 $...$ 原样
    assert "$R_G$" in ax.get_xlabel() or "R_G" in ax.get_xlabel()


# ---------------- 内嵌子图 ----------------


def test_inset_sits_inside_parent():
    fig = _paper_figure()
    fig.add_inset(1, parent=0)
    fig.add_plot("line", x=[0, 1, 2], y=[0, 1, 4], subplot=1)
    rendered = mpl_backend.to_figure(fig.spec, fig.store, dpi=100)
    parent_ax = rendered.axes[0]
    assert parent_ax.child_axes, "inset 应当挂在父轴上"
    parent, child = parent_ax.get_position(), parent_ax.child_axes[0].get_position()
    assert parent.x0 <= child.x0 <= parent.x1
    assert parent.y0 <= child.y0 <= parent.y1


def test_inset_does_not_consume_grid_slot():
    fig = _paper_figure()
    fig.add_inset(1, parent=0)
    fig.add_plot("line", x=[0, 1], y=[0, 1], subplot=1)
    fig.add_plot("line", x=[0, 1], y=[1, 0], subplot=2)
    assert fig.spec["figure"]["subplots"] == 2  # figure 层记的是网格槽数
    assert len(fig.spec["figure"]["insets"]) == 1


# ---------------- 端到端 ----------------


def test_paper_figure_renders_to_png():
    fig = _paper_figure()
    fig.add_inset(1, parent=0)
    fig.add_plot("line", x=[0, 1, 2], y=[0, 1, 4], subplot=1)
    fig.validate()
    assert fig.png(dpi=96)[:8] == b"\x89PNG\r\n\x1a\n"


def test_style_whitelist_keeps_unknown_in_warnings():
    spec = {
        "figure": {},
        "layers": [{"kind": "line", "data": {}, "style": {"bogus_key": 1}}],
    }
    report = v.validate_spec(spec)
    assert any("bogus_key" in i.message for i in report.warnings)


def test_alias_kind_is_valid_in_spec():
    fig = pk.figure()
    fig.add_plot("scatter", x=[1, 2], y=[1, 2])
    fig.validate()  # scatter 是 marker 的别名，不应报错


def test_validate_accepts_alias_kind():
    spec = {"figure": {}, "layers": [{"kind": "scatter", "data": {}, "style": {}}]}
    report = v.validate_spec(spec)
    assert not [i for i in report.errors if "kind" in i.message]
