"""P13-00 基建：mpl 渲染管线 + ETag 缓存 + presets / add / strict（D33–D36）。"""

from __future__ import annotations

import struct

import numpy as np
import pytest
from fastapi.testclient import TestClient

import plotkit as pk
from plotkit.server.app import create_app


def _png_size(payload: bytes) -> tuple[int, int]:
    assert payload[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", payload[16:24])
    return int(width), int(height)


@pytest.fixture()
def fig() -> pk.Figure:
    f = pk.figure(size=(6.0, 4.0))
    t = np.linspace(0.0, 1.0, 200)
    f.add_data("t", t, unit="s", role="coord")
    f.add_data("v", np.sin(6.0 * t), unit="V", role="series")
    f.add_plot("line", x="t", y="v", label="v")
    return f


@pytest.fixture()
def client(fig) -> TestClient:
    return TestClient(create_app(fig))


def test_render_returns_png_with_requested_pixels(fig):
    payload = fig.render(width=640, height=360)
    assert _png_size(payload) == (640, 360)


def test_render_is_byte_stable(fig):
    """同一 spec + 同一视窗两次渲染必须逐字节一致（像素快照回归的前提）。"""
    assert fig.render(width=480, height=300) == fig.render(width=480, height=300)


def test_render_xlim_changes_pixels_and_reports_limits(fig):
    base = fig.render(width=480, height=300)
    zoomed, limits = fig.render(width=480, height=300, xlim=(0.0, 0.25), with_limits=True)
    assert zoomed != base
    assert limits["xlim"] == [0.0, 0.25]
    assert limits["box"][2] > 0.5 and limits["box"][3] > 0.5


def test_render_t_end_truncates(fig):
    full = fig.render(width=400, height=260)
    cut = fig.render(width=400, height=260, t_end=0.3)
    assert cut != full


def test_render_svg(fig):
    payload = fig.render(width=320, height=200, fmt="svg")
    assert b"<svg" in payload[:400]


def test_render_endpoint_headers_and_etag(client):
    first = client.get("/api/render", params={"w": 400, "h": 260})
    assert first.status_code == 200
    assert first.headers["content-type"] == "image/png"
    assert first.headers["x-plotkit-render"] == "miss"
    assert first.headers["x-plotkit-xlim"] and first.headers["x-plotkit-box"]
    tag = first.headers["etag"]

    second = client.get("/api/render", params={"w": 400, "h": 260})
    assert second.headers["x-plotkit-render"] == "hit"
    assert second.headers["etag"] == tag

    third = client.get("/api/render", params={"w": 400, "h": 260}, headers={"If-None-Match": tag})
    assert third.status_code == 304


def test_render_cache_invalidates_when_spec_changes(client, fig):
    tag = client.get("/api/render", params={"w": 320, "h": 200}).headers["etag"]
    fig.spec["figure"]["title"] = "改标题"
    after = client.get("/api/render", params={"w": 320, "h": 200})
    assert after.headers["etag"] != tag
    assert after.headers["x-plotkit-render"] == "miss"


def test_render_rejects_bad_arguments(client):
    assert client.get("/api/render", params={"fmt": "pdf"}).status_code == 400
    assert client.get("/api/render", params={"xlim": "5,1"}).status_code == 400
    assert client.get("/api/render", params={"xlim": "1"}).status_code == 400


def test_render_clamps_size(client):
    res = client.get("/api/render", params={"w": 10, "h": 10})
    assert res.status_code == 200
    assert _png_size(res.content) == (80, 60)


def test_presets_apply_before_explicit_style(fig):
    layer = fig.add_plot("bar", x=np.arange(3), y=np.arange(3), label="b")
    assert layer["style"]["mode"] == "bars"
    assert layer["style"]["width"] == 0.8
    assert fig.layers()[0]["style"]["mode"] == "lines"  # 预设按 kind 区分


def test_add_dispatches_like_multiplotter():
    f = pk.figure()
    layer = f.add("line", {"x": np.arange(4), "y": np.arange(4) * 2, "color": "#ff0000", "label": "l"})
    assert layer["kind"] == "line"
    assert layer["style"]["color"] == "#ff0000"
    assert layer["data"]["x"] and layer["data"]["y"]
    # P13-01 起 pie 也走同一入口
    pie = f.add("pie", {"labels": ["a", "b"], "values": [1, 2]})
    assert pie["kind"] == "pie" and pie["data"]["values"]
    with pytest.raises(ValueError):
        f.add("pie", {"labels": ["a"]})  # 缺 values


def test_strict_mode_raises_on_unknown_style():
    f = pk.figure(strict=True)
    with pytest.raises(ValueError):
        f.add_plot("line", x=np.arange(3), y=np.arange(3), zorder=3)
    # 非严格模式只记 warning
    g = pk.figure()
    g.add_plot("line", x=np.arange(3), y=np.arange(3), zorder=3)
    assert g.warnings and "zorder" in g.warnings[0]


def test_init_defaults_apply_to_layers():
    f = pk.figure(defaults={"xlabel": "t / s", "grid": False})
    layer = f.add_plot("line", x=np.arange(3), y=np.arange(3))
    assert layer["view"]["xlabel"] == "t / s"
    assert layer["view"]["grid"] is False
    explicit = f.add_plot("line", x=np.arange(3), y=np.arange(3), view={"xlabel": "x"})
    assert explicit["view"]["xlabel"] == "x"
