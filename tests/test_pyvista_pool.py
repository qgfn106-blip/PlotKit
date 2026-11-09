"""进程池批量出图：结果必须与单进程逐字节一致，且在批量任务上确实更快。"""

from __future__ import annotations

import numpy as np
import pytest

import plotkit as pk
from plotkit.backends import pyvista_backend, pyvista_pool


def _has_pyvista() -> bool:
    try:
        __import__("pyvista")
        return True
    except Exception:  # noqa: BLE001 - 未安装可选依赖
        return False


requires_pyvista = pytest.mark.skipif(not _has_pyvista(), reason="未安装 pyvista")
pytestmark = requires_pyvista  # 3 个用例全部依赖 pyvista；仍被收集、缺 extra 时逐个 skip


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
        fig.spec,
        fig.store,
        width=220,
        height=160,
        dpi=100,
        fmt="png",
        xlim=None,
        ylim=None,
        with_limits=False,
    ).payload
    assert len(pooled) == 2
    assert pooled[0] == single  # 逐字节一致：同一份 spec 同一台机器
    assert pooled[1] == single


def test_render_many_empty_is_noop():
    assert pyvista_pool.render_many([]) == []


def test_workers_default_is_bounded():
    n = pyvista_pool.workers_default()
    assert 1 <= n <= 8
