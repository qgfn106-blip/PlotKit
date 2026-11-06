"""PK-R20 自由布局：`figure.layout` 让子图按 rect 摆放、允许互相重叠。

约定：
- rect = [x, y, w, h]，figure 比例（0..1，y 从下往上）；
- 不写 layout 时行为与原来的网格完全一致（旧 spec 不用改）；
- 没写进 layout 的槽位退回网格位置，不会消失。
"""

from __future__ import annotations

import pytest

import plotkit as pk
from plotkit.backends import mpl_backend
from plotkit.spec.validate import validate_spec


def _two_slot_figure(**kwargs):
    fig = pk.figure(ncols=2, subplots=2, **kwargs)
    fig.add_plot(x=[0, 1, 2], y=[1, 2, 3], subplot=0)
    fig.add_plot(x=[0, 1, 2], y=[3, 2, 1], subplot=1)
    return fig


def _boxes(mpl_fig):
    return [
        tuple(round(float(v), 3) for v in ax.get_position().bounds)
        for ax in mpl_fig.axes
    ]


def test_free_layout_places_slots_at_rects_and_allows_overlap() -> None:
    fig = _two_slot_figure()
    fig.spec["figure"]["layout"] = [
        {"slot": 0, "rect": [0.05, 0.10, 0.60, 0.80]},
        {"slot": 1, "rect": [0.35, 0.30, 0.60, 0.60]},
    ]

    assert validate_spec(fig.spec).ok

    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert _boxes(mpl_fig) == [(0.05, 0.1, 0.6, 0.8), (0.35, 0.3, 0.6, 0.6)]


def test_grid_layout_unchanged_without_layout_key() -> None:
    fig = _two_slot_figure()

    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    boxes = _boxes(mpl_fig)
    assert len(boxes) == 2
    # 网格两列：左轴在左半边、右轴在右半边，且不重叠
    assert boxes[0][0] < boxes[1][0]
    assert boxes[0][0] + boxes[0][2] <= boxes[1][0]


def test_slots_missing_from_layout_fall_back_to_grid() -> None:
    fig = _two_slot_figure()
    fig.spec["figure"]["layout"] = [{"slot": 0, "rect": [0.05, 0.10, 0.60, 0.80]}]

    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    boxes = _boxes(mpl_fig)
    assert boxes[0] == (0.05, 0.1, 0.6, 0.8)
    # 槽 1 没写进 layout，仍在画布内、且宽度是正的
    assert 0 <= boxes[1][0] <= 1 and boxes[1][2] > 0 and boxes[1][3] > 0


@pytest.mark.parametrize(
    "layout",
    [
        [{"slot": 0, "rect": [0.0, 0.0, 0.0, 0.5]}],
        [{"slot": 0, "rect": [0.0, 0.0, 0.5]}],
        [{"slot": -1, "rect": [0.0, 0.0, 0.5, 0.5]}],
        [{"slot": "0", "rect": [0.0, 0.0, 0.5, 0.5]}],
        [
            {"slot": 0, "rect": [0.0, 0.0, 0.5, 0.5]},
            {"slot": 0, "rect": [0.1, 0.1, 0.2, 0.2]},
        ],
        [{"slot": 0, "rect": [0.9, 0.9, 0.8, 0.8]}],
    ],
)
def test_layout_validation_rejects_bad_rects(layout) -> None:
    fig = _two_slot_figure()
    fig.spec["figure"]["layout"] = layout

    assert not validate_spec(fig.spec).ok


def test_server_render_reports_free_layout_boxes() -> None:
    """端到端契约：PUT 带 layout 的 spec → /api/render 的 X-PlotKit-Axes 反映 rect。"""
    from fastapi.testclient import TestClient
    from plotkit.server.app import create_app

    fig = _two_slot_figure()
    client = TestClient(create_app(fig))
    spec = dict(fig.spec)
    spec["figure"] = dict(spec["figure"])
    spec["figure"]["layout"] = [
        {"slot": 0, "rect": [0.05, 0.10, 0.60, 0.80]},
        {"slot": 1, "rect": [0.35, 0.30, 0.60, 0.60]},
    ]
    put = client.put("/api/spec", json=spec)
    assert put.status_code == 200, put.text

    res = client.get("/api/render", params={"w": 640, "h": 400})
    assert res.status_code == 200
    axes = res.headers.get("X-PlotKit-Axes", "")
    boxes = {}
    for chunk in axes.split(";"):
        if not chunk:
            continue
        slot, *nums = chunk.split(",")
        boxes[int(slot)] = [round(float(v), 3) for v in nums]
    assert boxes[0] == [0.05, 0.1, 0.6, 0.8]
    assert boxes[1] == [0.35, 0.3, 0.6, 0.6]


def test_static_page_exposes_free_layout_controls() -> None:
    """前端入口存在：按钮、覆盖层、以及 enableFreeLayout 真的写 figure.layout。"""
    from pathlib import Path

    static = Path(__file__).resolve().parents[1] / "src" / "plotkit" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    js = (static / "app.js").read_text(encoding="utf-8")

    assert 'id="btn-free-layout"' in html
    assert 'id="btn-grid-layout"' in html
    assert 'id="layout-overlay"' in html
    assert "function enableFreeLayout" in js
    assert "fig.layout = layout" in js
    assert "function renderLayoutOverlay" in js
    assert "拖拽子图" in js
