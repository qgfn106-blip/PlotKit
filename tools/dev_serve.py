"""开发用：起一个带样例数据的 PlotKit 服务，阻塞到 Ctrl+C。

    PYTHONPATH=src python tools/dev_serve.py --port 8791
"""

from __future__ import annotations

import argparse
import time

import numpy as np

import plotkit as pk
from plotkit.server.live import LiveServer


def demo() -> pk.Figure:
    t = np.linspace(0, 1, 8001)
    fig = pk.figure(title="自检 · 双子图", size=(11, 6), theme="netlab-dark", ncols=2, subplots=2)
    fig.add_data("t", t, unit="s", role="coord", tags=["时间"])
    fig.add_data("vin", np.where(t < 0.05, 5.0, 0.0), unit="V", role="series", tags=["输入"])
    fig.add_data("vout", 5 * (1 - np.exp(-t / 0.09)), unit="V", role="series", tags=["输出"])
    fig.add_plot("line", x="t", y="vin", label="Vin", subplot=0, color="#ff8a65")
    fig.add_plot("line", x="t", y="vout", label="Vout", subplot=0, color="#4fc3f7")
    fig.add_plot("line", x="t", y="vout", label="Vout（对数轴）", subplot=1, color="#81c784")
    fig.set_view(1, yscale="log")
    fig.add_plot("bar", x=[0.2, 0.5, 0.8], y=[3, 7, 5], label="柱", subplot=1, opacity=0.55)
    fig.set_view(0, xlabel="t / s", ylabel="V / V")
    fig.set_view(1, xlabel="类别 / t", ylabel="V / V")
    return fig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8791)
    args = parser.parse_args()

    server = LiveServer(demo(), port=args.port)
    server.start()
    print(f"serving {server.url}  (Ctrl+C 结束)")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
