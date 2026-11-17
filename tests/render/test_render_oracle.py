"""渲染 oracle：已知曲线/批注位置与结构断言，并提供已知错位负例。

这些测试不依赖外部 baseline 图片，而是从 PNG 像素和 SVG 结构推导已知几何关系：
- 曲线：y=x 的蓝色像素必须形成一条从轴左下到右上的近直线，拟合斜率与跨度符合预期；
- 批注：位于 figure 中心的 text note 必须落在中心像素区域，移到角落后必须不落在这里；
- 结构：SVG 必须包含预期的轴刻度、轴标签和标题文本。
"""

from __future__ import annotations

import io
import re

import numpy as np
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
Image = pytest.importorskip("PIL.Image")
matplotlib = pytest.importorskip("matplotlib")

from fastapi.testclient import TestClient  # noqa: E402
from plotkit.api.native import figure  # noqa: E402
from plotkit.server.app import create_app  # noqa: E402
from plotkit.spec.model import new_note  # noqa: E402


def _figure(*, v=None, notes=None):
    fig = figure(title="Oracle")
    t = np.linspace(0.0, 1.0, 21)
    values = np.linspace(0.0, 1.0, 21) if v is None else np.asarray(v, dtype=float)
    fig.add_data("t", t, unit="s", role="coord")
    fig.add_data("v", values, unit="V", role="series")
    fig.add_plot("line", x="t", y="v")
    fig.set_view(0, xlim=(0, 1), ylim=(0, 1), xlabel="Time t / s", ylabel="Amp / V")
    if notes:
        fig.update_layout(notes=notes)
    return fig


def _client(fig, tmp_path):
    return TestClient(create_app(fig, layout_path=tmp_path / "layout.json"))


def _get(client, *, w=400, h=300, dpi=60, fmt="png"):
    try:
        return client.get(
            "/api/render",
            params={"w": w, "h": h, "dpi": dpi, "fmt": fmt},
            headers={"Accept-Encoding": "identity"},
        )
    except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover
        pytest.skip(f"渲染后端不可用：{exc}")


def _png_array(response):
    if response.status_code == 501:  # pragma: no cover
        pytest.skip("该后端未提供 PNG 渲染")
    assert response.status_code == 200, response.text[:300]
    assert response.headers["content-type"].startswith("image/png")
    return np.asarray(Image.open(io.BytesIO(response.content)).convert("RGB")).astype(int)


def _curve_geometry(response):
    """提取曲线像素并返回几何度量；ok=False 表示未通过已知 y=x 的 oracle。"""
    arr = _png_array(response)
    h, w = arr.shape[:2]
    # PlotKit 默认蓝色曲线 #4fc3f7 及其抗锯齿像素；避开白/灰背景。
    mask = (arr[:, :, 2] > 200) & (arr[:, :, 1] > 150) & (arr[:, :, 0] < 150)
    ys, xs = np.nonzero(mask)
    if len(xs) < 20:
        return {"ok": False, "reason": "too few curve pixels", "n": int(len(xs))}
    slope, intercept = np.polyfit(xs, ys, 1)
    corr = float(np.corrcoef(xs, ys)[0, 1])
    span_x = (int(xs.max()) - int(xs.min())) / (w - 1)
    span_y = (int(ys.max()) - int(ys.min())) / (h - 1)
    # 已知曲线跨满 x/y 轴；y 像素向下，故斜率应为负且约 -0.7。
    ok = (
        corr < -0.98
        and -0.95 < float(slope) < -0.45
        and span_x > 0.75
        and span_y > 0.60
    )
    return {
        "ok": ok,
        "n": int(len(xs)),
        "slope": float(slope),
        "intercept": float(intercept),
        "corr": corr,
        "span_x": float(span_x),
        "span_y": float(span_y),
    }


def _teal_mask(arr):
    return (
        (arr[:, :, 0] < 80)
        & (arr[:, :, 1] > 70)
        & (arr[:, :, 1] < 160)
        & (arr[:, :, 2] > 70)
        & (arr[:, :, 2] < 160)
    )


def _note_center_region(response):
    arr = _png_array(response)
    h, w = arr.shape[:2]
    mask = _teal_mask(arr)
    ys, xs = np.nonzero(mask)
    region = (xs >= int(0.45 * w)) & (xs <= int(0.80 * w)) & (ys >= int(0.35 * h)) & (ys <= int(0.55 * h))
    count = int(region.sum())
    return {"count": count, "ok": count >= 50, "centroid": (float(xs[region].mean()), float(ys[region].mean())) if count else None}


def test_known_curve_matches_geometry_oracle(tmp_path):
    response = _get(_client(_figure(), tmp_path))
    geometry = _curve_geometry(response)
    assert geometry["ok"], geometry
    assert geometry["corr"] < -0.99
    assert -0.85 < geometry["slope"] < -0.55


def test_curve_geometry_oracle_rejects_wrong_curve(tmp_path):
    # 已知错位负例：数据只上升到 0.35，几何 oracle 必须拒绝。
    wrong = _figure(v=np.linspace(0.0, 0.35, 21))
    geometry = _curve_geometry(_get(_client(wrong, tmp_path)))
    assert geometry["ok"] is False, geometry
    assert geometry.get("span_y", 0.0) < 0.60 or not (-0.95 < geometry.get("slope", 0) < -0.45)


def test_note_position_oracle_center(tmp_path):
    note = new_note("text", text="CENTER", pos=(0.5, 0.5), size=18)
    result = _note_center_region(_get(_client(_figure(notes=[note]), tmp_path)))
    assert result["ok"], result


def test_note_position_oracle_rejects_corner_note(tmp_path):
    note = new_note("text", text="CORNER", pos=(0.02, 0.98), size=18)
    result = _note_center_region(_get(_client(_figure(notes=[note]), tmp_path)))
    assert result["ok"] is False, result
    assert result["count"] == 0


def test_svg_structure_contains_known_ticks_axes_and_title(tmp_path):
    client = _client(_figure(), tmp_path)
    with matplotlib.rc_context({"svg.fonttype": "none"}):
        response = _get(client, w=400, h=300, fmt="svg")
    if response.status_code == 501:  # pragma: no cover
        pytest.skip("该后端未提供 SVG 渲染")
    assert response.status_code == 200, response.text[:300]
    assert response.headers["content-type"].startswith("image/svg+xml")
    text = response.content.decode("utf-8")
    labels = re.findall(r"<text[^>]*>(.*?)</text>", text, flags=re.S)
    # 已知刻度与轴标签/标题必须出现在 SVG 文本层，而不是仅作为图像存在。
    for expected in ("0.0", "0.4", "0.6", "1.0", "Time t / s", "Amp / V", "Oracle"):
        assert expected in labels, (expected, labels)
    assert "<image" not in text
