"""视窗（viewport）裁剪：必须先切窗口再转换/抽稀，避免全量复制。"""

from __future__ import annotations

import tracemalloc

import numpy as np

from plotkit.backends.series import _xy, _window_slice
from plotkit.store.registry import DataStore


def _layer(x_name="t", y_name="y", **extra):
    data = {"x": x_name, "y": y_name}
    data.update(extra)
    return {"id": "L0", "kind": "line", "data": data, "style": {}}


def _store(n=200_000):
    store = DataStore(namespace="t")
    t = np.arange(n, dtype=np.float64)
    store.add("t", t, role="coord")
    store.add("y", np.sin(t / 100.0), role="series")
    return store


def test_window_slice_monotonic():
    x = np.arange(100.0)
    assert _window_slice(x, (10.0, 19.0)) == (10, 20)
    assert _window_slice(x, None) == (0, 100)
    assert _window_slice(np.array([]), (0, 1)) == (0, 0)


def test_window_slice_non_monotonic_falls_back():
    x = np.array([0.0, 5.0, 1.0, 7.0, 3.0])
    i0, i1 = _window_slice(x, (1.0, 5.0))
    assert (i0, i1) == (1, 5)     # 从第一个命中到最后一个命中之后
    assert _window_slice(x, (100.0, 200.0)) == (0, 0)


def test_xy_window_only_returns_window_points():
    store = _store()
    x, y = _xy(_layer(), store, pixels=None, per_pixel=2.0, trange=(1000.0, 1999.0))
    assert len(x) == 1000
    assert x[0] == 1000.0 and x[-1] == 1999.0


def test_xy_window_downsamples_only_window():
    store = _store()
    x, _ = _xy(_layer(), store, pixels=100, per_pixel=2.0, trange=(50_000.0, 59_999.0))
    assert len(x) <= 100 * 2 + 2
    assert 50_000.0 <= x[0] <= 50_100.0
    assert 59_900.0 <= x[-1] <= 59_999.0


def test_xy_window_peak_memory_is_window_sized():
    store = _store(1_000_000)
    tracemalloc.start()
    _xy(_layer(), store, pixels=120, per_pixel=2.0, trange=(500_000.0, 500_999.0))
    _, peak_window = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    tracemalloc.start()
    _xy(_layer(), store, pixels=120, per_pixel=2.0)
    _, peak_full = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert peak_window < peak_full / 4, (peak_window, peak_full)


def test_error_bars_respect_window():
    store = _store()
    store.add("err", np.full(200_000, 0.5), role="series")
    out = _xy(_layer(error_y="err"), store, pixels=None, per_pixel=2.0, trange=(10.0, 19.0))
    assert len(out[0]) == 10


def test_xy_dtype_kept_when_not_downsampling():
    store = DataStore(namespace="t")
    store.add("t", np.arange(100, dtype=np.float32), role="coord")
    store.add("y", np.arange(100, dtype=np.float32), role="series")
    x, y = _xy(_layer(), store, pixels=None, per_pixel=2.0)
    assert x.dtype == np.float64 and y.dtype == np.float64


# ---- 端到端：render(t_end=...) 不得再复制整份 store ----

def _line_figure(t: np.ndarray, y: np.ndarray):
    import plotkit as pk

    fig = pk.figure(size=(6.0, 3.0), dpi=100)
    fig.add_data("t", t, role="coord")
    fig.add_data("y", y, role="series")
    fig.add_plot(x="t", y="y")
    return fig


def test_render_t_end_matches_truncated_store():
    t = np.arange(20_000, dtype=float)
    y = np.sin(t / 100.0)
    got = _line_figure(t, y).render(width=600, height=360, t_end=9_999.0)
    want = _line_figure(t[:10_000], y[:10_000]).render(width=600, height=360)
    assert got == want


def test_render_t_end_with_window_matches_tail():
    t = np.arange(20_000, dtype=float)
    y = np.sin(t / 100.0)
    fig = _line_figure(t, y)
    fig.window(999.0)                      # [t_end-999, t_end]
    got = fig.render(width=600, height=360, t_end=9_999.0)
    want = _line_figure(t[9_000:10_000], y[9_000:10_000]).render(width=600, height=360)
    assert got == want


def test_render_t_end_avoids_store_copy(monkeypatch):
    import plotkit as pk

    t = np.arange(50_000, dtype=float)
    fig = _line_figure(t, np.sin(t / 100.0))

    def boom(self, t_end):                  # noqa: ANN001
        raise AssertionError("可切片的图层不应走 _store_at 整体复制")

    monkeypatch.setattr(pk.Figure, "_store_at", boom)
    assert fig.render(width=400, height=300, t_end=1_000.0)[:8] == b"\x89PNG\r\n\x1a\n"
