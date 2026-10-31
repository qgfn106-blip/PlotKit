"""持久 Figure 热重绘缓存：命中后输出必须与无状态重建逐像素一致。"""

from __future__ import annotations

import io

import matplotlib.image as mpimg
import numpy as np
import pytest

import plotkit as pk
from plotkit.backends import livecache


@pytest.fixture(autouse=True)
def _clean_cache():
    livecache.get_cache().clear()
    livecache.get_cache().hits = 0
    livecache.get_cache().misses = 0
    yield
    livecache.get_cache().clear()


def _pixels(png: bytes) -> np.ndarray:
    return mpimg.imread(io.BytesIO(png))


def _line_figure(y: np.ndarray):
    t = np.arange(y.size, dtype=float)
    fig = pk.figure(size=(4.0, 2.5), dpi=100)
    fig.add_data("t", t, role="coord")
    fig.add_data("y", y, role="series")
    fig.add_plot(x="t", y="y")
    return fig


def _limits(n: int) -> dict:
    return {"xlim": (0.0, float(n - 1)), "ylim": (-2.0, 2.0)}


def _fresh(y: np.ndarray, *, limits: bool, width: int = 400, height: int = 250) -> bytes:
    fig = _line_figure(y)
    kw = _limits(y.size) if limits else {}
    return fig.render(width=width, height=height, **kw)


def test_hit_produces_pixels_identical_to_full_render():
    y = np.sin(np.arange(500) / 20.0)
    fig = _line_figure(y)
    fig.render(width=400, height=250, **_limits(y.size))   # 填充缓存
    got = fig.render(width=400, height=250, **_limits(y.size))
    assert livecache.get_cache().hits >= 1
    assert np.array_equal(_pixels(got), _pixels(_fresh(y, limits=True)))


def test_hit_after_data_change_matches_full_render():
    y1 = np.sin(np.arange(500) / 20.0)
    y2 = np.cos(np.arange(500) / 15.0)
    fig = _line_figure(y1)
    fig.render(width=400, height=250, **_limits(y1.size))
    fig.store.add("y", y2, role="series", life="replace", overwrite=True)   # spec 不变，只换数据
    got = fig.render(width=400, height=250, **_limits(y2.size))
    assert livecache.get_cache().hits >= 1
    assert np.array_equal(_pixels(got), _pixels(_fresh(y2, limits=True)))


def test_autoscale_path_matches_full_render():
    y = np.sin(np.arange(800) / 30.0)
    fig = _line_figure(y)
    fig.render(width=400, height=250)
    fig.store.add("y", y * 3.0, role="series", life="replace", overwrite=True)
    got = fig.render(width=400, height=250)
    assert np.array_equal(_pixels(got), _pixels(_fresh(y * 3.0, limits=False)))


def test_spec_change_invalidates():
    y = np.sin(np.arange(300) / 10.0)
    fig = _line_figure(y)
    fig.render(width=400, height=250, **_limits(y.size))
    before = livecache.get_cache().hits
    fig.spec["layers"][0].setdefault("style", {})["color"] = "#ff0000"
    got = fig.render(width=400, height=250, **_limits(y.size))
    assert livecache.get_cache().hits == before
    assert got[:8] == b"\x89PNG\r\n\x1a\n"


def test_bar_falls_back_to_rebuild():
    x = np.arange(6.0)
    fig = pk.figure(size=(4.0, 2.5), dpi=100)
    fig.add_data("x", x, role="coord")
    fig.add_data("v", np.array([3.0, 5.0, 2.0, 7.0, 4.0, 6.0]), role="series")
    fig.add_plot("bar", x="x", y="v")
    first = fig.render(width=400, height=250)
    second = fig.render(width=400, height=250)
    assert np.array_equal(_pixels(first), _pixels(second))


def test_render_still_bytewise_stable_between_identical_calls():
    y = np.sin(np.arange(400) / 12.0)
    fig = _line_figure(y)
    a = fig.render(width=400, height=250, **_limits(y.size))
    b = fig.render(width=400, height=250, **_limits(y.size))
    assert a == b           # 同一 spec + 同一视窗，两次渲染必须逐字节一致
