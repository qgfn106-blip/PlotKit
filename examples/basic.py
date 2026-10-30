"""最小例子：一条 RC 充电曲线，交互 + 静态两种出口。

    python examples/basic.py
    python examples/basic.py --sink browser
"""

from __future__ import annotations

import argparse

import numpy as np

import plotkit as pk


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sink", default=None, help="inline / window / browser（默认自动探测）")
    parser.add_argument("--save", default=None, help="额外导出一张 PNG")
    args = parser.parse_args()

    t = np.linspace(0.0, 1.0, 2001)
    v_out = 5.0 * (1.0 - np.exp(-t / 0.2))

    fig = pk.figure(title="RC 充电 · 5V 阶跃", size=(11, 6), theme="netlab-dark")
    fig.add_data("t", t, unit="s", role="coord", tags=["时间"])
    fig.add_data("v_out", v_out, unit="V", role="series", tags=["输出", "电压"])
    fig.add_plot("line", x="t", y="v_out", label="V_out", color="#4fc3f7", lw=2.0)
    fig.set_view(0, xlabel="时间 t / s", ylabel="电压 V_out / V", ylim=[0, 5.5])
    fig.layers()[0]["annotations"].append({"type": "hline", "y": 5.0, "color": "#ff8a65"})

    if args.save:
        fig.savefig(args.save, dpi=150)
        print(f"已导出 {args.save}")

    fig.show(sink=args.sink)


if __name__ == "__main__":
    main()
