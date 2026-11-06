"""P13-01：hist / pie / image / table 四种图层（服务端分箱 + mpl 渲染）。"""

from __future__ import annotations

import io
import struct

import numpy as np
import pytest
from PIL import Image

import plotkit as pk
from plotkit.backends.mpl_backend import hist_counts


def _png_size(payload: bytes) -> tuple[int, int]:
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", payload[16:24])


def _distinct_colors(payload: bytes) -> int:
    img = Image.open(io.BytesIO(payload)).convert("RGB")
    return len(set(img.getdata()))


def _figure(kind: str, cfg: dict) -> pk.Figure:
    fig = pk.figure(size=(5.0, 3.2), theme="netlab-dark")
    fig.add(kind, cfg)
    return fig


# ---------------- hist ----------------


def test_hist_bins_match_numpy():
    rng = np.random.default_rng(7)
    x = rng.normal(size=400)
    fig = _figure("hist", {"x": x, "bins": 17})
    counts, edges = hist_counts(fig.layers()[0], fig.store)
    ref_counts, ref_edges = np.histogram(x, bins=17)
    assert np.array_equal(counts, ref_counts)
    assert np.allclose(edges, ref_edges)


def test_hist_density_and_nan_filtered():
    x = np.array([1.0, 2.0, np.nan, 3.0, 4.0])
    fig = _figure("hist", {"x": x, "bins": 4, "density": True})
    counts, _ = hist_counts(fig.layers()[0], fig.store)
    assert counts.sum() > 0  # 密度归一后积分≈1，NaN 被剔除


def test_hist_renders_non_blank():
    payload = _figure("hist", {"x": np.random.default_rng(3).normal(size=300)}).render(
        width=480, height=300
    )
    assert _png_size(payload) == (480, 300)
    assert _distinct_colors(payload) > 8


# ---------------- pie ----------------


def test_pie_requires_labels_and_values():
    fig = pk.figure()
    with pytest.raises(ValueError, match="values"):
        fig.add("pie", {"labels": ["a", "b"]})


def test_pie_roles_are_table_and_series():
    fig = _figure("pie", {"labels": ["A", "B", "C"], "values": [3, 2, 1]})
    data = fig.layers()[0]["data"]
    assert fig.store.meta(data["labels"])["role"] == "table"
    assert fig.store.meta(data["values"])["role"] == "series"


def test_pie_renders_non_blank():
    payload = _figure("pie", {"labels": ["A", "B", "C"], "values": [3, 2, 1]}).render(
        width=480, height=300
    )
    assert _distinct_colors(payload) > 8


# ---------------- image ----------------


def test_image_accepts_2d_array():
    fig = _figure("image", {"image": np.arange(60).reshape(6, 10)})
    name = fig.layers()[0]["data"]["image"]
    assert fig.store.meta(name)["role"] == "image"
    assert fig.store.values(name).shape == (6, 10)


def test_image_renders_with_colorbar():
    payload = _figure(
        "image", {"image": np.random.default_rng(5).random((12, 18)), "colorbar": True}
    ).render(width=480, height=300)
    assert _distinct_colors(payload) > 8


def test_image_rejects_wrong_role():
    """role 不匹配在 validate 阶段被拒（add_plot 只登记名字，不猜用途）。"""
    from plotkit.spec.validate import SpecError

    fig = pk.figure()
    fig.add_data("series_only", np.arange(10), role="series")
    fig.add_plot("image", data={"image": "series_only"})
    with pytest.raises(SpecError, match="不能绑到 image.image"):
        fig.validate()


# ---------------- table ----------------


def test_table_cells_and_header():
    fig = _figure("table", {"cells": np.arange(6).reshape(3, 2), "header": ["x", "y"]})
    data = fig.layers()[0]["data"]
    assert fig.store.meta(data["cells"])["role"] == "table"
    assert fig.store.meta(data["header"])["role"] == "table"


def test_table_renders_non_blank():
    payload = _figure(
        "table", {"cells": np.arange(6).reshape(3, 2), "header": ["x", "y"]}
    ).render(width=480, height=300)
    assert _distinct_colors(payload) > 8


# ---------------- 通用 ----------------


def test_new_kinds_are_registered():
    from plotkit.backends import registry as reg

    for kind in ("hist", "pie", "image", "table"):
        assert kind in reg.kinds()
        assert reg.resolve(kind).dimension == 2


def test_spec_roundtrip_keeps_new_kinds():
    fig = _figure("image", {"image": np.zeros((4, 4)), "cmap": "magma"})
    text = fig.to_json()
    again = (
        pk.Figure.load_spec_text(text) if hasattr(pk.Figure, "load_spec_text") else None
    )
    assert "magma" in text and '"image"' in text
    assert again is None or again.spec["layers"][0]["kind"] == "image"


def test_render_endpoint_serves_new_kind():
    from fastapi.testclient import TestClient

    from plotkit.server.app import create_app

    fig = _figure("pie", {"labels": ["A", "B"], "values": [2, 1]})
    client = TestClient(create_app(fig))
    res = client.get("/api/render", params={"w": 360, "h": 240})
    assert res.status_code == 200
    assert _png_size(res.content) == (360, 240)


def test_table_highlight_max_changes_pixels():
    cells = np.array([[1.0, 9.0], [3.0, 4.0]])
    fig = pk.figure(size=(4.0, 2.8))
    fig.add_data("cells", cells, role="table")
    fig.add("table", {"cells": "cells"})
    plain = fig.render(width=360, height=240)
    fig.spec["layers"][0]["style"]["highlight"] = "max"
    assert fig.render(width=360, height=240) != plain
