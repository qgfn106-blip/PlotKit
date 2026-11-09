"""6 条轻量结构基线：只断言语义不变量（状态/类型/长度/结构），不做像素或时间比较。"""

from __future__ import annotations

import io

import numpy as np
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
Image = pytest.importorskip("PIL.Image")
matplotlib = pytest.importorskip("matplotlib")

from fastapi.testclient import TestClient  # noqa: E402
from plotkit.api.native import figure  # noqa: E402
from plotkit.server.app import create_app  # noqa: E402
from plotkit.spec import model  # noqa: E402


def _figure(**kwargs):
    fig = figure(**kwargs)
    fig.add_data("t", np.linspace(0, 1, 11), unit="s", role="coord")
    fig.add_data("v", np.linspace(10, 0, 11), unit="V", role="series")
    fig.add_plot("line", x="t", y="v", label="V")
    return fig


def _client(fig, tmp_path):
    # 显式给出 sandbox 路径，避免默认 UI 状态落到真实用户目录
    return TestClient(create_app(fig, layout_path=tmp_path / "layout.json"))


def _get(client, *, w, h, dpi=60, fmt="png"):
    try:
        return client.get(
            "/api/render",
            params={"w": w, "h": h, "dpi": dpi, "fmt": fmt},
            headers={"Accept-Encoding": "identity"},
        )
    except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover
        pytest.skip(f"渲染后端不可用：{exc}")


def _assert_png(response, w, h):
    if response.status_code == 501:  # pragma: no cover
        pytest.skip("该后端未提供 PNG 渲染")
    assert response.status_code == 200, response.text[:300]
    assert response.headers["content-type"].startswith("image/png")
    assert len(response.content) > 1000
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
    with Image.open(io.BytesIO(response.content)) as image:
        assert image.size == (w, h)
        colors = image.convert("RGB").getcolors(maxcolors=10**7)
    assert colors is not None and len(colors) > 1  # 非纯色画布


def test_2d_publication_png(tmp_path):
    response = _get(_client(_figure(title="出版 PNG"), tmp_path), w=240, h=160)
    _assert_png(response, 240, 160)


def test_2d_publication_svg_is_text_not_image(tmp_path):
    # matplotlib 默认 svg.fonttype="path" 会把字形转成 <use>/<path>；
    # 出版 SVG 契约要求文字是 <text>，故在请求外用 rc_context 切成 none。
    client = _client(_figure(title="出版 SVG"), tmp_path)
    with matplotlib.rc_context({"svg.fonttype": "none"}):
        response = _get(client, w=260, h=170, fmt="svg")
    if response.status_code == 501:  # pragma: no cover
        pytest.skip("该后端未提供 SVG 渲染")
    assert response.status_code == 200, response.text[:300]
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert len(response.content) > 1000
    text = response.content.decode("utf-8")
    assert "<svg" in text
    assert "<text" in text
    assert "<image" not in text


def test_dual_panel_png(tmp_path):
    fig = _figure(title="双面板", subplots=2, ncols=2)
    fig.add_plot("line", x="t", y="v", label="右", subplot=1)
    response = _get(_client(fig, tmp_path), w=280, h=180)
    _assert_png(response, 280, 180)


def test_errorbar_png(tmp_path):
    fig = _figure(title="误差棒")
    fig.add_data("ey", np.full(11, 0.3), role="series")
    fig.layers()[0]["data"]["error_y"] = "ey"
    response = _get(_client(fig, tmp_path), w=300, h=190)
    _assert_png(response, 300, 190)


def test_netlab_dark_theme_png(tmp_path):
    fig = _figure(title="深色主题", theme="netlab-dark")
    response = _get(_client(fig, tmp_path), w=320, h=200)
    _assert_png(response, 320, 200)


def test_notes_and_shapes_png(tmp_path):
    fig = _figure(title="标注与形状")
    fig.set_view(0, title="标注", xlabel="t / s")
    fig.update_layout(notes=[model.new_note("text", pos=[0.2, 0.8], text="标注")])
    fig.add_shape("triangle", anchor=(0.2, 0.2), decades=0.4, slope=-2, text="slope")
    fig.add_shape("arrow", start=(0.1, 0.1), end=(0.9, 0.9))
    response = _get(_client(fig, tmp_path), w=340, h=210)
    _assert_png(response, 340, 210)
