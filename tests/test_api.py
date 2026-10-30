import json

import numpy as np
import pytest

import plotkit as pk


def strip_ids(spec):
    out = json.loads(json.dumps(spec))
    for layer in out["layers"]:
        layer["id"] = "X"
    return out


def test_figure_defaults():
    fig = pk.figure(title="t")
    assert fig.spec["figure"]["title"] == "t"
    assert fig.spec["layers"] == []
    fig.validate()  # 空 spec 也合法


def test_add_plot_with_arrays_registers_anon_dataset():
    fig = pk.figure()
    fig.add_plot("line", x=[0, 1, 2], y=[1, 4, 9], label="sq")
    assert len(fig.layers()) == 1
    refs = fig.layers()[0]["data"]
    assert refs["x"].startswith("anon_")
    assert fig.store.values(refs["y"]).tolist() == [1, 4, 9]


def test_add_plot_requires_xy():
    fig = pk.figure()
    with pytest.raises(ValueError):
        fig.add_plot("line", x=[0, 1])


def test_add_plot_unknown_kind_fails_fast():
    fig = pk.figure()
    with pytest.raises(KeyError):
        fig.add_plot("surface", x=[0], y=[1])


def test_style_aliases_map_to_spec():
    fig = pk.figure()
    layer = fig.add_plot("line", x=[0, 1], y=[1, 2], c="#ff0000", lw=3.0, alpha=0.5)
    assert layer["style"]["color"] == "#ff0000"
    assert layer["style"]["width"] == 3.0
    assert layer["style"]["opacity"] == 0.5


def test_unknown_kwargs_warn_but_do_not_fail():
    fig = pk.figure()
    with pytest.warns(UserWarning):
        fig.add_plot("line", x=[0, 1], y=[1, 2], rasterized=True)
    assert any("rasterized" in w for w in fig.warnings)


def test_three_entry_points_share_one_spec():
    fig_a = pk.figure(size=(10, 6))
    fig_a.add_data("t", [0, 1, 2], role="coord")
    fig_a.add_data("v", [3, 4, 5], role="series")
    fig_a.add_plot("line", x="t", y="v", label="V", color="#4fc3f7")

    fig_b = pk.figure(size=(10, 6))
    fig_b.store.add("t", [0, 1, 2], role="coord")
    fig_b.store.add("v", [3, 4, 5], role="series")
    fig_b.add_trace({"type": "scatter", "x": "t", "y": "v", "name": "V",
                     "line": {"color": "#4fc3f7"}})

    fig_c, axes = pk.subplots(1, 1, size=(10, 6))
    fig_c.store.add("t", [0, 1, 2], role="coord")
    fig_c.store.add("v", [3, 4, 5], role="series")
    axes[0].plot("t", "v", label="V", color="#4fc3f7")

    assert strip_ids(fig_a.to_spec()) == strip_ids(fig_b.to_spec()) == strip_ids(fig_c.to_spec())


def test_update_layout_and_traces():
    fig = pk.figure()
    fig.add_plot("line", x=[0, 1], y=[1, 2], label="a")
    fig.update_layout(title="新标题", ncols=2, subplots=2, link_x=True)
    fig.update_traces(lw=4.0)
    assert fig.spec["figure"]["title"] == "新标题"
    assert fig.layers()[0]["style"]["width"] == 4.0
    fig.update_layout(xlabel="时间")
    assert fig.layers()[0]["view"]["xlabel"] == "时间"


def test_validate_catches_unknown_dataset():
    fig = pk.figure()
    fig.add_plot("line", x=[0, 1], y=[1, 2])
    fig.store.remove(fig.layers()[0]["data"]["y"])
    with pytest.raises(pk.spec.SpecError):
        fig.validate()


def test_save_and_load_spec(tmp_path):
    fig = pk.figure(title="保存")
    fig.add_plot("line", x=[0, 1], y=[1, 2], label="a")
    path = fig.save_spec(tmp_path / "spec.json")
    reloaded = pk.Figure.load_spec(path)
    assert strip_ids(reloaded.to_spec()) == strip_ids(fig.to_spec())


def test_plotly_output_is_json_serializable():
    fig = pk.figure()
    fig.add_plot("line", x=np.linspace(0, 1, 5), y=np.linspace(0, 1, 5))
    payload = fig.plotly()
    json.dumps(payload)  # 不抛异常即通过


def test_png_bytes_nonempty():
    fig = pk.figure()
    fig.add_plot("bar", x=[0, 1, 2], y=[3, 1, 2], label="bars")
    payload = fig.png(dpi=70)
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"


def test_html_is_self_contained():
    fig = pk.figure()
    fig.add_plot("line", x=[0, 1], y=[1, 2])
    html = fig.html()
    assert "plotly.js (basic" in html
    # 没有任何外链脚本/样式：断网也能打开
    assert "<script src=" not in html
    assert "<link rel=\"stylesheet\"" not in html


def test_set_default_store_switches_proxy():
    original = pk.default_store()
    try:
        fresh = pk.DataStore(namespace="alt")
        pk.set_default_store(fresh)
        fresh.add("v", [1, 2])
        assert "v" in pk.data.names()
        # Figure 默认自带 store；要共享就显式传
        assert pk.figure().store is not fresh
        assert pk.figure(store=fresh).store is fresh
    finally:
        pk.set_default_store(original)


def test_remove_layer_and_clear():
    fig = pk.figure()
    layer = fig.add_plot("line", x=[0, 1], y=[1, 2])
    fig.remove_layer(layer["id"])
    assert fig.layers() == []
    fig.add_plot("line", x=[0, 1], y=[1, 2])
    fig.clear()
    assert fig.layers() == []


def test_subplots_grid_geometry():
    fig, axes = pk.subplots(2, 3)
    assert fig.spec["figure"]["ncols"] == 3
    assert fig.spec["figure"]["subplots"] == 6
    assert len(axes) == 6
    assert axes[4].index == 4


def test_axes_proxy_implicit_index():
    fig, axes = pk.subplots(1, 1)
    store = fig.store
    store.add("v", [5, 6, 7], role="series")
    axes[0].plot("v")
    refs = fig.layers()[0]["data"]
    assert "idx_v" in store
    assert store.values(refs["x"]).tolist() == [0.0, 1.0, 2.0]


def test_annotation_without_layer_warns():
    fig, axes = pk.subplots(1, 1)
    axes[0].axhline(0.5)
    assert any("标注" in w for w in fig.warnings)
    assert fig.layers() == []
