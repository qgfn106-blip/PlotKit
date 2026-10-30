import numpy as np
import pytest

import plotkit as pk
from plotkit.backends import registry as reg
from plotkit.backends import mpl_backend, plotly_backend
from plotkit.spec.model import new_layer, new_spec


def make_figure(n=50, *, subplot=0):
    store = pk.DataStore()
    t = np.linspace(0, 1, n)
    store.add("t", t, role="coord", unit="s")
    store.add("v", 1 - np.exp(-t / 0.2), role="series", unit="V")
    spec = new_spec(ncols=2, subplots=2)
    spec["layers"].append(new_layer("line", subplot=subplot, data={"x": "t", "y": "v"}, label="V"))
    return spec, store


# ---------------- registry ----------------
def test_v0_kinds_registered():
    assert {"line", "marker", "bar"} <= set(reg.kinds())
    assert reg.resolve("scatter").kind == "marker"


def test_unknown_kind_raises():
    with pytest.raises(KeyError):
        reg.resolve("surface")


def test_duplicate_register_needs_overwrite():
    with pytest.raises(ValueError):
        reg.register("line", 2, None)


def test_describe_reports_builder_presence():
    items = {d["kind"]: d for d in reg.describe()}
    assert items["line"]["has_builder"] is True
    assert items["line"]["dimension"] == 2


# ---------------- plotly ----------------
def test_plotly_trace_shape():
    spec, store = make_figure()
    fig = plotly_backend.to_figure(spec, store)
    assert len(fig["data"]) == 1
    trace = fig["data"][0]
    assert trace["type"] == "scatter"
    assert trace["mode"] == "lines"
    assert len(trace["x"]) == 50
    assert trace["name"] == "V"


def test_plotly_axes_per_subplot():
    spec, store = make_figure(subplot=1)
    fig = plotly_backend.to_figure(spec, store)
    assert "xaxis2" in fig["layout"]
    assert fig["data"][0]["xaxis"] == "x2"  # trace 侧用 x2 引用 layout.xaxis2
    assert fig["layout"]["xaxis2"]["domain"][0] >= 0.5


def test_plotly_layout_is_autosize_and_axes_are_anchored():
    """浏览器后端不能写死像素宽高，且 anchor 必须用轴 id（x2/y2）而不是 layout 键名。

    这两个都是真实渲染时暴露出来的 bug：写死 width=1100 会把右侧面板挤出屏幕；
    anchor 写成 "xaxis2" 会让第二个子图的 y 轴画到最左边、和第一个子图重叠。
    """
    spec, store = make_figure(subplot=1)
    fig = plotly_backend.to_figure(spec, store)
    assert "width" not in fig["layout"] and "height" not in fig["layout"]
    assert fig["layout"]["autosize"] is True
    assert fig["layout"]["xaxis2"]["anchor"] == "y2"
    assert fig["layout"]["yaxis2"]["anchor"] == "x2"


def test_plotly_bar_width_is_not_line_width():
    store = pk.DataStore()
    store.add("x", [0, 1, 2], role="coord")
    store.add("y", [3, 7, 5], role="series")
    spec = new_spec()
    spec["layers"].append(new_layer("bar", data={"x": "x", "y": "y"}))
    fig = plotly_backend.to_figure(spec, store)
    # 默认 0.6 个坐标单位；不能拿 line 的 width=1.6 当柱宽（会把柱子糊满整张图）
    assert fig["data"][0]["width"] == 0.6


def test_plotly_nan_becomes_null():
    store = pk.DataStore()
    store.add("t", [0, 1, 2], role="coord")
    store.add("v", [1.0, np.nan, 3.0], role="series")
    spec = new_spec()
    spec["layers"].append(new_layer("line", data={"x": "t", "y": "v"}))
    fig = plotly_backend.to_figure(spec, store)
    assert fig["data"][0]["y"] == [1.0, None, 3.0]


def test_plotly_bar_and_scatter_modes():
    store = pk.DataStore()
    store.add("t", [0, 1], role="coord")
    store.add("v", [1, 2], role="series")
    spec = new_spec()
    spec["layers"].append(new_layer("bar", data={"x": "t", "y": "v"}))
    spec["layers"].append(new_layer("marker", data={"x": "t", "y": "v"}))
    fig = plotly_backend.to_figure(spec, store)
    assert fig["data"][0]["type"] == "bar"
    assert fig["data"][1]["mode"] == "markers"


def test_plotly_downsample_respects_pixels():
    spec, store = make_figure(n=200_000)
    fig = plotly_backend.to_figure(spec, store, pixels=400)
    assert len(fig["data"][0]["x"]) <= 808


def test_plotly_color_cycle_stable():
    spec, store = make_figure()
    spec["layers"].append(new_layer("line", subplot=1, data={"x": "t", "y": "v"}))
    fig = plotly_backend.to_figure(spec, store)
    assert fig["data"][0]["line"]["color"] == plotly_backend.color_for(0)
    assert fig["data"][1]["line"]["color"] == plotly_backend.color_for(1)


def test_plotly_annotations_mapped():
    spec, store = make_figure()
    spec["layers"][0]["annotations"] = [
        {"type": "hline", "y": 0.5},
        {"type": "text", "x": 0.1, "y": 0.9, "text": "峰值"},
    ]
    fig = plotly_backend.to_figure(spec, store)
    # 横线走 shapes；文字走 mode="text" 的 trace（layout.annotations 在部分 bundle 下整组不渲染）
    assert any(s.get("type") == "line" for s in fig["layout"]["shapes"])
    texts = [t for t in fig["data"] if t.get("mode") == "text"]
    assert any("峰值" in str(t.get("text")) for t in texts)


def test_plotly_theme_dark():
    spec, store = make_figure()
    spec["figure"]["theme"] = "netlab-dark"
    fig = plotly_backend.to_figure(spec, store)
    assert fig["layout"]["paper_bgcolor"] == plotly_backend.THEMES["netlab-dark"]["paper"]


# ---------------- matplotlib ----------------
def test_mpl_savefig_png(tmp_path):
    spec, store = make_figure()
    target = tmp_path / "a.png"
    mpl_backend.savefig(spec, store, target, dpi=80)
    assert target.exists() and target.stat().st_size > 1000


def test_mpl_savefig_svg(tmp_path):
    spec, store = make_figure()
    target = mpl_backend.savefig(spec, store, tmp_path / "a.svg")
    assert "<svg" in target.read_text(encoding="utf-8")[:2000]


def test_mpl_two_subplots_have_two_axes():
    spec, store = make_figure()
    spec["layers"].append(new_layer("bar", subplot=1, data={"x": "t", "y": "v"}))
    fig = mpl_backend.to_figure(spec, store)
    visible = [ax for ax in fig.axes if ax.get_visible()]
    assert len(visible) == 2


def test_mpl_unsupported_kind_raises():
    store = pk.DataStore()
    store.add("t", [0, 1], role="coord")
    store.add("v", [1, 2], role="series")
    spec = new_spec()
    layer = new_layer("line", data={"x": "t", "y": "v"})
    layer["kind"] = "not-implemented"
    spec["layers"].append(layer)
    with pytest.raises(ValueError):
        mpl_backend.to_figure(spec, store)
