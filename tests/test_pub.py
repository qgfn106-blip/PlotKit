"""论文级出图能力（v0.2）：误差棒 / 对数轴 / 刻度 / 字号 / 装饰 / 内嵌子图。

这一组测试对应用户给的 panel b 参考图要求，钉住"同一份 spec、两个后端"的公共语义。
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import plotkit as pk
from plotkit.backends import plotly_backend, registry
from plotkit.spec import validate as v


def _paper_figure() -> pk.Figure:
    x = np.linspace(1.4, 10.0, 12)
    y = 0.5 * x ** -3.0
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


# ---------------- 误差棒 ----------------


def test_error_bars_are_attached_to_trace():
    fig = _paper_figure()
    data = fig.plotly(pixels=800)["data"][0]
    assert data["error_y"]["array"] is not None
    assert data["error_x"]["array"] is not None
    assert data["error_y"]["thickness"] >= 1.0
    assert data["error_y"]["width"] >= 1.0


def test_error_bars_skip_downsampling():
    x = np.linspace(0, 10, 5000)
    y = np.sin(x)
    fig = pk.figure()
    fig.add_data("x", x)
    fig.add_data("y", y)
    fig.add_data("e", np.full_like(x, 0.1))
    fig.add_plot("line", x=x, y=y)
    fig.layers()[0]["data"]["error_y"] = "e"
    data = fig.plotly(pixels=400)["data"][0]
    assert len(data["y"]) == len(y)  # 抽稀会破坏误差数组对齐，必须原样给


def test_asymmetric_error_uses_minus_arrow():
    x = np.linspace(0, 1, 5)
    fig = pk.figure()
    fig.add_data("x", x)
    fig.add_data("y", x)
    fig.add_data("up", np.full(5, 0.2))
    fig.add_data("down", np.full(5, 0.05))
    fig.add_plot("scatter", x=x, y=x)
    layer = fig.layers()[0]
    layer["data"].update({"error_y": "up", "error_y_minus": "down"})
    data = fig.plotly()["data"][0]
    assert data["error_y"]["arrayminus"] is not None


# ---------------- 对数轴 ----------------


def test_log_range_is_expressed_as_exponents():
    fig = _paper_figure()
    layout = fig.plotly()["layout"]
    lo, hi = layout["xaxis"]["range"]
    assert lo == pytest.approx(math.log10(1.3))
    assert hi == pytest.approx(math.log10(11.0))
    assert layout["xaxis"]["type"] == "log"


def test_log_range_rejects_nonpositive():
    fig = pk.figure()
    fig.add_plot("line", x=[1, 2], y=[1, 2])
    fig.set_view(0, xscale="log", xlim=(0.0, 5.0))
    with pytest.raises(ValueError):
        fig.plotly()


# ---------------- 刻度与字号 ----------------


def test_ticks_inside_mirror_and_fonts():
    fig = _paper_figure()
    fig.spec["figure"]["fonts"] = {"axis": 15, "tick": 9}
    layout = fig.plotly()["layout"]
    xaxis = layout["xaxis"]
    assert xaxis["ticks"] == "inside"
    assert xaxis["mirror"] == "all"
    assert xaxis["tickfont"]["size"] == pytest.approx(9)
    assert xaxis["title"]["font"]["size"] == pytest.approx(15)


def test_minor_ticks_toggle():
    fig = pk.figure()
    fig.add_plot("line", x=[1, 2], y=[1, 2])
    fig.set_view(0, xscale="log", ticks={"minor": True})
    assert fig.plotly()["layout"]["xaxis"].get("minor") is not None
    fig.set_view(0, ticks={"minor": False})
    assert not fig.plotly()["layout"]["xaxis"].get("minor")


# ---------------- 装饰 ----------------


def test_triangle_and_arrow_shapes():
    fig = pk.figure()
    fig.add_plot("scatter", x=[1, 2], y=[1, 2])
    fig.add_shape("triangle", anchor=(1.2, 1.0), decades=0.5, slope=-3, text="−3")
    fig.add_shape("arrow", start=(1.5, 0.5), end=(1.5, 2.0), text="ρ_B")
    payload = fig.plotly()
    assert len(payload["layout"]["shapes"]) >= 3  # 三角形是三段线
    texts = [str(t.get("text")) for t in payload["data"] if t.get("mode") == "text"]
    assert any("3" in t for t in texts)
    assert any("ρ" in t for t in texts)


def test_math_text_conversion():
    assert plotly_backend.math_text("$R_G$") == "R<sub>G</sub>"
    assert plotly_backend.math_text(r"$\Delta\theta^2$") == "Δθ<sup>2</sup>"
    assert "<sub>" not in plotly_backend.math_text("plain")


# ---------------- 内嵌子图 ----------------


def test_inset_domain_sits_inside_parent():
    fig = _paper_figure()
    fig.add_inset(1, parent=0, rect=(0.6, 0.6, 0.3, 0.3))
    fig.add_plot("line", x=[0, 1, 2], y=[0, 1, 4], subplot=1)
    layout = fig.plotly()["layout"]
    parent = layout["xaxis"]["domain"]
    child = layout["xaxis2"]["domain"]
    assert parent[0] <= child[0] <= parent[1]
    assert parent[0] <= child[1] <= parent[1]


def test_inset_axis_anchor_points_at_its_own_pair():
    fig = _paper_figure()
    fig.add_inset(1, parent=0)
    fig.add_plot("line", x=[0, 1], y=[0, 1], subplot=1)
    layout = fig.plotly()["layout"]
    # 写 "xaxis2" 会让轴落回最左边；必须是轴 id "y2"
    assert layout["xaxis2"]["anchor"] == "y2"
    assert layout["yaxis2"]["anchor"] == "x2"


def test_inset_does_not_consume_grid_slot():
    fig = _paper_figure()
    fig.add_inset(1, parent=0)
    fig.add_plot("line", x=[0, 1], y=[0, 1], subplot=1)
    fig.add_plot("line", x=[0, 1], y=[1, 0], subplot=2)
    # 子图槽位 2 仍在主网格里（不因为 inset 占位而错位）
    assert fig.spec["figure"]["subplots"] == 2  # figure 层记的是网格槽数
    assert len(fig.spec["figure"]["insets"]) == 1


# ---------------- 后端一致性 ----------------


def test_both_backends_render_the_same_spec():
    fig = _paper_figure()
    fig.add_inset(1, parent=0)
    fig.add_plot("line", x=[0, 1, 2], y=[0, 1, 4], subplot=1)
    fig.validate()

    png = fig.png(dpi=96)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"

    payload = fig.plotly()
    assert payload["data"] and payload["layout"]


def test_mpl_draws_errorbars_and_inset_axes():
    fig = _paper_figure()
    fig.add_inset(1, parent=0)
    fig.add_plot("line", x=[0, 1, 2], y=[0, 1, 4], subplot=1)
    from plotkit.backends.mpl_backend import to_figure

    mpl_fig = to_figure(fig.spec, fig.store, dpi=96)
    # matplotlib 的 inset_axes 是"子轴"，挂在父轴的 child_axes 里，不进 fig.axes
    parent = mpl_fig.axes[0]
    assert len(parent.child_axes) == 1
    assert len(parent.collections) >= 2  # 误差棒的线 + 端帽


def test_style_whitelist_keeps_unknown_in_warnings():
    fig = pk.figure()
    with pytest.warns(UserWarning):
        fig.add_plot("line", x=[0, 1], y=[0, 1], style={"color": "#123456", "bogus": 1})
    style = fig.layers()[0]["style"]
    assert style["color"] == "#123456"
    assert "bogus" not in style


def test_alias_kind_is_valid_in_spec():
    spec = {"spec_version": "0.1", "figure": {"subplots": 1, "ncols": 1}, "layers": [
        {"id": "l1", "kind": "scatter", "subplot": 0, "data": {"x": "x", "y": "y"}},
    ]}
    assert "scatter" in registry.known_kind_names()


def test_validate_accepts_alias_kind():
    array = np.linspace(0, 1, 4)
    store = pk.DataStore()
    store.add("x", array)
    store.add("y", array)
    spec = {"spec_version": "0.1", "figure": {"subplots": 1, "ncols": 1}, "layers": [
        {"id": "l1", "kind": "scatter", "subplot": 0, "data": {"x": "x", "y": "y"},
         "style": {}, "view": {}},
    ]}
    report = v.validate_spec(spec, store=store, known_kinds=registry.known_kind_names())
    assert report.ok
