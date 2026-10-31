"""PK-R13 完整性：`pk.init()` / `pk.style_scope()` / `pk.register_layer()` / 透传白名单。"""

from __future__ import annotations

import numpy as np
import pytest

import plotkit as pk
from plotkit.backends import registry as reg


@pytest.fixture(autouse=True)
def _clean_global_style():
    """init() 是进程级状态：每个用例前后都清空，避免相互污染。"""
    pk.reset_style()
    yield
    pk.reset_style()


def test_init_applies_view_and_style_defaults():
    pk.init(width=3.0, color="#ff0000", grid=False, xlabel="t/s")
    fig = pk.figure()
    layer = fig.add_plot("line", x=np.arange(3), y=np.arange(3))
    assert layer["style"]["width"] == 3.0
    assert layer["style"]["color"] == "#ff0000"
    assert layer["view"]["grid"] is False
    assert layer["view"]["xlabel"] == "t/s"


def test_init_defaults_lose_to_explicit_args_but_win_over_presets():
    pk.init(width=3.0, mode="markers")  # 覆盖 line 预设 mode=lines
    fig = pk.figure()
    auto = fig.add_plot("line", x=np.arange(3), y=np.arange(3))
    assert auto["style"]["mode"] == "markers"  # init > KIND_PRESETS
    assert auto["style"]["width"] == 3.0
    explicit = fig.add_plot("line", x=np.arange(3), y=np.arange(3), width=1.0, mode="lines")
    assert explicit["style"]["width"] == 1.0   # 显式 > init
    assert explicit["style"]["mode"] == "lines"


def test_style_scope_overrides_then_restores():
    pk.init(width=2.0)
    with pk.style_scope(width=5.0, grid=False):
        inner = pk.figure().add_plot("line", x=[0, 1], y=[0, 1])
        assert inner["style"]["width"] == 5.0
        assert inner["view"]["grid"] is False
    after = pk.figure().add_plot("line", x=[0, 1], y=[0, 1])
    assert after["style"]["width"] == 2.0  # 退出后还原，grid 也回默认 True
    assert after["view"]["grid"] is True


def test_style_scope_restores_on_exception():
    pk.init(width=2.0)
    with pytest.raises(RuntimeError):
        with pk.style_scope(width=9.0):
            raise RuntimeError("boom")
    assert pk.global_style()["width"] == 2.0


def test_figure_defaults_kwarg_beats_global_init():
    pk.init(width=3.0)
    layer = pk.figure(defaults={"width": 1.5}).add_plot("line", x=[0, 1], y=[0, 1])
    assert layer["style"]["width"] == 1.5


def _make_custom_kind(name: str, *, passthrough=(), preset=None):
    def _build(ax, layer, store, index, *, pixels=None, per_pixel=2.0):
        ax.plot([0, 1], [1, 0])

    spec = pk.register_layer(
        name, 2, builder=_build, passthrough=passthrough, preset=preset,
        description="测试用自定义 kind", overwrite=True,
    )
    return spec


@pytest.fixture
def custom_kind():
    name = "test_custom_line"
    yield name, _make_custom_kind(name, passthrough=("zorder", "rasterized"),
                                  preset={"style": {"width": 2.5}, "view": {}})
    reg.LAYER_SPECS.pop(name, None)
    for alias, target in list(reg.ALIASES.items()):
        if target == name:
            reg.ALIASES.pop(alias, None)


def test_register_layer_registers_capability_and_preset(custom_kind):
    name, spec = custom_kind
    assert name in pk.kinds()
    described = {d["kind"]: d for d in pk.describe()}
    assert described[name]["passthrough"] == ["zorder", "rasterized"]
    # 预设生效
    layer = pk.figure().add_plot(name, x=[0, 1], y=[0, 1])
    assert layer["style"]["width"] == 2.5


def test_passthrough_whitelist_accepts_extra_kwargs(custom_kind):
    name, _ = custom_kind
    fig = pk.figure(strict=True)  # strict 下也不该抛
    layer = fig.add_plot(name, x=[0, 1], y=[0, 1], zorder=7, rasterized=True)
    assert layer["style"]["passthrough"] == {"zorder": 7, "rasterized": True}
    assert fig.warnings == []
    # 能真的渲染出图（builder 被调用）
    payload = fig.render(width=320, height=200)
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"


def test_passthrough_not_whitelisted_still_ignored():
    fig = pk.figure()
    fig.add_plot("line", x=[0, 1], y=[0, 1], zorder=7)  # line 未声明 passthrough
    assert fig.warnings and "zorder" in fig.warnings[0]
    assert "passthrough" not in fig.layers()[0]["style"]


def test_register_layer_unknown_kind_via_add_still_fails_fast():
    with pytest.raises(KeyError):
        pk.figure().add_plot("definitely_not_a_kind", x=[0, 1], y=[0, 1])
