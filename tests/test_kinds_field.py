"""P13-02：场类图层（heatmap / contour / contourf / correlation）。"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

import plotkit as pk
from plotkit.backends import mpl_backend


def _grid(rows: int = 12, cols: int = 16, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    x = np.linspace(-2, 2, cols)
    y = np.linspace(-1, 1, rows)
    return np.sin(x[None, :] * 2) * np.cos(y[:, None] * 3) + rng.normal(
        scale=0.05, size=(rows, cols)
    )


def _figure(kind: str, cfg: dict) -> pk.Figure:
    fig = pk.figure(size=(5.2, 3.4), theme="netlab-dark")
    fig.add(kind, cfg)
    return fig


def _colors(payload: bytes) -> int:
    return len(set(Image.open(io.BytesIO(payload)).convert("RGB").getdata()))


# ---------------- heatmap ----------------


def test_heatmap_renders_with_colorbar():
    fig = _figure("heatmap", {"z": _grid()})
    payload = fig.render(width=480, height=320)
    assert _colors(payload) > 32
    # colorbar 会多出一个 axes
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=100)
    assert len(mpl_fig.axes) == 2


def test_heatmap_with_explicit_xy_uses_pcolormesh():
    fig = _figure(
        "heatmap",
        {"z": _grid(6, 8), "x": np.linspace(0, 1, 8), "y": np.linspace(0, 2, 6)},
    )
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=100)
    main = mpl_fig.axes[0]
    assert main.collections, "pcolormesh 应产生 QuadMesh"
    mesh = main.collections[0]
    assert mesh.get_array().shape == (6, 8)


def test_heatmap_requires_z():
    with pytest.raises(ValueError, match="z"):
        pk.figure().add("heatmap", {"x": np.arange(3)})


# ---------------- contour ----------------


def test_contour_levels_honoured():
    """传显式 levels 列表时必须逐条生效（传整数只是"建议值"，mpl 会自行取整）。"""
    levels = [-1.0, -0.5, 0.0, 0.5, 1.0]
    fig = _figure("contour", {"z": _grid(), "levels": levels})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=100)
    cs = mpl_fig.axes[0].collections[0]
    assert list(cs.levels) == levels


def test_contour_labels_add_text():
    fig = _figure("contour", {"z": _grid(), "labels": True})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=100)
    assert mpl_fig.axes[0].texts, "labels=True 应调用 clabel 生成文字"


def test_contourf_is_filled():
    fig = _figure("contourf", {"z": _grid(), "levels": 6})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=100)
    cs = mpl_fig.axes[0].collections[0]
    assert cs.filled is True


def test_contour_renders_non_blank():
    assert (
        _colors(_figure("contour", {"z": _grid()}).render(width=420, height=280)) > 16
    )


# ---------------- correlation ----------------


def test_correlation_matrix_matches_numpy():
    rng = np.random.default_rng(11)
    cols = [rng.normal(size=50) for _ in range(4)]
    fig = pk.figure(size=(4.5, 3.6))
    layer = fig.add_correlation(
        {"a": cols[0], "b": cols[1], "c": cols[2], "d": cols[3]}
    )
    matrix = np.asarray(fig.store.values(layer["data"]["z"]))
    ref = np.corrcoef(np.vstack(cols))
    assert matrix.shape == (4, 4)
    assert np.allclose(matrix, ref, atol=1e-12)
    assert layer["kind"] == "correlation"


def test_correlation_uses_diverging_defaults():
    fig = pk.figure()
    layer = fig.add_correlation({"a": np.arange(10.0), "b": np.arange(10.0) ** 2})
    assert layer["style"]["vmin"] == -1 and layer["style"]["vmax"] == 1
    assert layer["style"]["cmap"] in ("RdBu_r", "coolwarm")


def test_correlation_aliases_resolve():
    from plotkit.backends import registry as reg

    for alias in ("corr", "correlation_matrix"):
        assert reg.resolve(alias).kind == "correlation"


# ---------------- 注册与校验 ----------------


def test_field_kinds_registered():
    from plotkit.backends import registry as reg

    for kind in ("heatmap", "contour", "contourf", "correlation"):
        assert kind in reg.kinds()
        assert reg.resolve(kind).dimension == 2


def test_heatmap_rejects_wrong_role():
    from plotkit.spec.validate import SpecError

    fig = pk.figure()
    fig.add_data("s", np.arange(9.0), role="series")
    fig.add_plot("heatmap", data={"z": "s"})
    with pytest.raises(SpecError, match="不能绑到 heatmap.z"):
        fig.validate()


def test_field_kinds_spec_roundtrip():
    """四件套第①项：spec 往返字节相等，未知字段保留。"""
    fig = _figure("heatmap", {"z": _grid(5, 6), "cmap": "magma", "vmin": -1, "vmax": 1})
    fig.layers()[0]["future_field"] = {"keep": True}
    import json

    first = fig.to_json()
    second = pk.Figure(spec=json.loads(first)).to_json()
    assert second == first
    assert "future_field" in second


def test_field_kind_survives_render_with_xlim():
    """改视窗后必须能重绘（前端缩放走的就是这条路）。"""
    fig = _figure("contourf", {"z": _grid(10, 12)})
    base = fig.render(width=420, height=280)
    zoomed = fig.render(width=420, height=280, xlim=(2.0, 6.0))
    assert zoomed != base
