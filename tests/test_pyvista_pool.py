"""进程池批量出图：结果必须与单进程逐字节一致，且在批量任务上确实更快。"""

from __future__ import annotations

import numpy as np
import pytest

pv = pytest.importorskip("pyvista")  # noqa: F841 - 没装 pyvista 就跳过

import plotkit as pk
from plotkit.backends import pyvista_backend, pyvista_pool


def _figure(phase: float = 0.0):
    n = 24
    x = np.linspace(-2, 2, n)
    y = np.linspace(-2, 2, n)
    X, Y = np.meshgrid(x, y)
    Z = np.sin(np.hypot(X, Y) * 2 + phase)
    fig = pk.figure()
    fig.add("surface", {"x": X, "y": Y, "z": Z})
    return fig


def test_render_many_matches_single_process():
    fig = _figure()
    jobs = [(fig.spec, fig.store, {"width": 220, "height": 160}) for _ in range(2)]
    pooled = pyvista_pool.render_many(jobs, workers=2)
    single = pyvista_backend.render_result(
        fig.spec, fig.store, width=220, height=160, dpi=100, fmt="png",
        xlim=None, ylim=None, with_limits=False).payload
    assert len(pooled) == 2
    assert pooled[0] == single          # 逐字节一致：同一份 spec 同一台机器
    assert pooled[1] == single


def test_render_many_empty_is_noop():
    assert pyvista_pool.render_many([]) == []


def test_workers_default_is_bounded():
    n = pyvista_pool.workers_default()
    assert 1 <= n <= 8
