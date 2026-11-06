"""带实时追加的例子：模拟仿真每步 push 一帧，浏览器里滚动更新。

    python examples/live_stream.py --sink browser

要点：
- `life="append"` 的数据集会被 push 追加，历史可回看；
- 前端只做视窗与交互，spec 改动才回后端（D2）；
- 这个脚本同时是 P5「接 netlab 时间序列页签」的预演。
"""

from __future__ import annotations

import argparse
import math
import threading
import time

import numpy as np

import plotkit as pk


def simulate(fig: pk.Figure, hz: float = 50.0, steps: int = 2000) -> None:
    dt = 1.0 / hz
    for i in range(steps):
        t = i * dt
        window = slice(max(0, i - 100), i + 1)
        t_arr = np.arange(0, i + 1) * dt
        v = (
            np.sin(2 * math.pi * 0.5 * t_arr) * 2.5
            + math.sin(2 * math.pi * 7 * t_arr) * 0.2
        )
        fig.store.push("t", np.array([t]))
        fig.store.push("v", np.array([v[-1]]))
        _ = window
        time.sleep(dt)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sink", default=None)
    parser.add_argument("--hz", type=float, default=50.0)
    args = parser.parse_args()

    fig = pk.figure(title="实时追加 · 50 Hz", size=(11, 5.5), theme="netlab-dark")
    fig.add_data("t", np.empty(0), unit="s", role="coord", life="append")
    fig.add_data("v", np.empty(0), unit="V", role="series", life="append")
    fig.add_plot("line", x="t", y="v", label="v(t)")
    fig.set_view(0, xlabel="t / s", ylabel="v / V")

    thread = threading.Thread(target=simulate, args=(fig, args.hz), daemon=True)
    thread.start()
    try:
        fig.show(sink=args.sink)
    finally:
        thread.join(timeout=1.0)


if __name__ == "__main__":
    main()
