"""跨版本兼容垫片的行为约束（2026-11-01 用户环境踩到 mpl 3.9+ 删了 cm.get_cmap）。"""

from __future__ import annotations

import numpy as np
import pytest

from plotkit._compat import get_cmap, trapezoid, versions


def test_get_cmap_returns_colormap():
    cmap = get_cmap("viridis")
    assert cmap.N > 1
    assert cmap(0.5) is not None


def test_get_cmap_default_when_none():
    assert get_cmap(None).N == get_cmap("viridis").N


def test_get_cmap_rejects_unknown_name():
    with pytest.raises(ValueError, match="colormap"):
        get_cmap("definitely-not-a-colormap")


def test_trapezoid_matches_reference():
    y = np.array([1.0, 1.0, 1.0])
    assert trapezoid(y, dx=1.0) == pytest.approx(2.0)
    # 分段梯形：0..2 段面积 2.0，2..3 段面积 1.0
    x = np.array([0.0, 2.0, 3.0])
    assert trapezoid(y, x=x) == pytest.approx(3.0)


def test_versions_reports_core_dependencies():
    env = versions()
    for key in ("python", "executable", "numpy", "matplotlib"):
        assert key in env and env[key] != "missing"
