"""进程池批量出图基准：串行 vs 2/4 worker。

注意：Windows 的 `spawn` 需要真实脚本文件（`if __name__ == "__main__":` 保护），
不能从 stdin/交互式里跑，否则子进程 import 不到主模块。
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import plotkit as pk  # noqa: E402
from plotkit.backends import pyvista_backend, pyvista_pool  # noqa: E402


def surface_figure(phase: float):
    n = 60
    x = np.linspace(-2, 2, n)
    y = np.linspace(-2, 2, n)
    X, Y = np.meshgrid(x, y)
    Z = np.sin(np.hypot(X, Y) * 2 + phase)
    fig = pk.figure()
    fig.add("surface", {"x": X, "y": Y, "z": Z})
    return fig


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", type=int, default=8)
    ap.add_argument("--width", type=int, default=500)
    ap.add_argument("--height", type=int, default=360)
    args = ap.parse_args()

    frames = [surface_figure(i * 0.1) for i in range(args.frames)]
    jobs = [(f.spec, f.store, {"width": args.width, "height": args.height}) for f in frames]

    def one(spec, store):
        return pyvista_backend.render_result(
            spec, store, width=args.width, height=args.height, dpi=100, fmt="png",
            xlim=None, ylim=None, with_limits=False).payload

    one(*jobs[0][:2])                      # 预热：首次要建 OpenGL 上下文

    t0 = time.perf_counter()
    serial = [one(spec, store) for spec, store, _ in jobs]
    t_serial = time.perf_counter() - t0
    print(f"serial {len(jobs)} frames: {t_serial * 1000:.0f} ms")

    for workers in (2, 4):
        t0 = time.perf_counter()
        pooled = pyvista_pool.render_many(jobs, workers=workers)
        t_pool = time.perf_counter() - t0
        same = all(a == b for a, b in zip(serial, pooled))
        print(f"pool {workers}w: {t_pool * 1000:.0f} ms  ({t_serial / t_pool:.2f}x)  identical={same}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
