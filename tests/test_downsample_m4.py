"""M4 降采样：语义与旧 minmax_envelope 对齐，实现更快更省内存。"""

from __future__ import annotations

import numpy as np
import pytest

from plotkit.store.downsample import (
    downsample_xy,
    get_downsample_backend,
    m4_envelope,
    minmax_envelope,
    set_downsample_backend,
)


@pytest.fixture(autouse=True)
def _restore_backend():
    old = get_downsample_backend()
    yield
    set_downsample_backend(old)


def test_m4_preserves_endpoints_and_peaks():
    n = 20_000
    x = np.arange(n, dtype=np.float64)
    y = np.sin(x / 100.0)
    y[12_345] = 99.0  # 单点尖峰
    y[7_777] = -42.0
    xo, yo = m4_envelope(x, y, 300)
    assert xo[0] == x[0] and xo[-1] == x[-1]
    assert yo.max() == 99.0 and yo.min() == -42.0


def test_m4_keeps_float32():
    x = np.arange(50_000, dtype=np.float32)
    y = np.sin(x).astype(np.float32)
    xo, yo = m4_envelope(x, y, 200)
    assert yo.dtype == np.float32
    assert xo.dtype == np.float32


def test_m4_output_size_bounded():
    x = np.arange(100_000, dtype=np.float64)
    y = np.cos(x / 50.0)
    xo, _ = m4_envelope(x, y, 400, per_pixel=2.0)
    assert len(xo) <= 400 * 2 + 2  # 两端点额外保留
    assert len(xo) > 100


def test_m4_short_input_passthrough():
    x = np.arange(10, dtype=np.float64)
    y = x * 2
    xo, yo = m4_envelope(x, y, 400)
    assert np.array_equal(xo, x) and np.array_equal(yo, y)


def test_m4_handles_all_nan_bucket():
    n = 10_000
    x = np.arange(n, dtype=np.float64)
    y = np.sin(x / 10.0)
    y[3_000:3_200] = np.nan  # 整段 NaN
    xo, yo = m4_envelope(x, y, 100)
    assert len(xo) > 0
    assert np.isfinite(yo).any()
    assert np.isnan(yo).sum() < 20  # 只保留桶起点，不会整段带出来


def test_m4_matches_minmax_global_envelope():
    rng = np.random.default_rng(7)
    x = np.arange(60_000, dtype=np.float64)
    y = np.cumsum(rng.normal(size=x.size))
    _, y_old = minmax_envelope(x, y, 500)
    _, y_new = m4_envelope(x, y, 500)
    assert y_old.min() == y_new.min()
    assert y_old.max() == y_new.max()


def test_backend_switch():
    x = np.arange(30_000, dtype=np.float64)
    y = np.sin(x / 30.0)
    set_downsample_backend("minmax")
    assert get_downsample_backend() == "minmax"
    xo_old, _ = downsample_xy(x, y, 300)
    set_downsample_backend("m4")
    xo_new, _ = downsample_xy(x, y, 300)
    assert len(xo_old) > 0 and len(xo_new) > 0
    assert xo_old[0] == xo_new[0] and xo_old[-1] == xo_new[-1]
    assert abs(len(xo_old) - len(xo_new)) < 50


def test_backend_rejects_unknown():
    with pytest.raises(ValueError):
        set_downsample_backend("bogus")


def test_downsample_xy_no_pixels_passthrough():
    x = np.arange(10.0)
    y = np.arange(10.0)
    xo, yo = downsample_xy(x, y, None)
    assert np.array_equal(xo, x) and np.array_equal(yo, y)
