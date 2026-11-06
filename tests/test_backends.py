import numpy as np
import pytest

import plotkit as pk
from plotkit.backends import registry as reg
from plotkit.backends import mpl_backend, series
from plotkit.spec.model import new_layer, new_spec


def make_figure(n=50, *, subplot=0):
    store = pk.DataStore()
    t = np.linspace(0, 1, n)
    store.add("t", t, role="coord", unit="s")
    store.add("v", 1 - np.exp(-t / 0.2), role="series", unit="V")
    spec = new_spec(ncols=2, subplots=2)
    spec["layers"].append(
        new_layer("line", subplot=subplot, data={"x": "t", "y": "v"}, label="V")
    )
    return spec, store


# ---------------- registry ----------------
def test_v0_kinds_registered():
    assert {"line", "marker", "bar"} <= set(reg.kinds())
    assert reg.resolve("scatter").kind == "marker"


def test_unknown_kind_raises():
    with pytest.raises(KeyError):
        reg.resolve("sankey")  # 未实现的 kind 作为反例


def test_duplicate_register_needs_overwrite():
    with pytest.raises(ValueError):
        reg.register("line", 2, None)


def test_describe_lists_every_kind():
    items = {d["kind"]: d for d in reg.describe()}
    assert items["line"]["dimension"] == 2
    assert items["surface"]["dimension"] == 3
    assert len(items) >= 50


# ---------------- 调色板与主题（原 plotly 后端，D33 迁到 series） ----------------
def test_color_cycle_is_stable():
    """调色板取色必须与图层序号绑定（不能随数据变）。"""
    assert series.color_for(0) != series.color_for(1)
    assert series.color_for(0) == series.color_for(0)


def test_themes_are_available():
    assert "netlab-dark" in series.THEMES
    assert series.THEMES["netlab-dark"]["paper"]


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
