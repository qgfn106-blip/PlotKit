"""论文级验收样本：复刻 MultiPlotter 用户的 panel b 结构。

要素清单（对照 docs/DESIGN_v0.md §15 的 pub 能力表）：
双对数 + 次刻度、内侧 + 四边镜像刻度、方向误差棒（带端帽）、4 组带描边 marker、
虚线幂律拟合、内嵌子图（父轴右上角）、斜率 −3 参考三角、箭头标注、逐级字号、LaTeX 上下标。

用法：
    python examples/paper_panel_b.py                # 只出 PNG（matplotlib，正式图）
    python examples/paper_panel_b.py --serve        # 起浏览器交互页（预览 + inset 拖拽）
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import plotkit as pk  # noqa: E402

# (marker, 颜色, 幂律系数 C) —— D = C · R_G^-3
SERIES = [
    ("square", "#1a1a1a", 0.030),
    ("diamond", "#e5813a", 0.105),
    ("triangle-up", "#7fa6cd", 0.042),
    ("circle", "#c0392b", 0.330),
]

RG = np.array([1.5, 1.8, 2.2, 2.6, 3.1, 3.7, 4.3, 5.2, 6.1, 7.1, 7.9, 8.6])


def build() -> pk.Figure:
    fig = pk.figure(
        size=(5.6, 4.4),
        dpi=200,
        ncols=1,
        subplots=2,          # 槽 0 = 主图；槽 1 = 内嵌图
        theme="default",
        fonts={"title": 13, "axis": 14, "tick": 11, "legend": 10, "annotation": 12},
    )
    fig.add_data("rg", RG, unit="μm", role="coord")

    for i, (symbol, color, coeff) in enumerate(SERIES):
        y = coeff * RG ** -3.0 * (1 + 0.04 * i)
        fig.add_data(f"d_{i}", y, unit="rad2/s", role="series", tags=["D_eff"])
        fig.add_data(f"xerr_{i}", RG * 0.06, unit="μm", role="coord")
        fig.add_data(f"yerr_{i}", y * 0.16, unit="rad2/s", role="series")
        fig.add_plot(
            "scatter",
            data={"x": "rg", "y": f"d_{i}", "error_x": f"xerr_{i}", "error_y": f"yerr_{i}"},
            legend=False,
            style={
                "color": color,
                "marker": {"symbol": symbol, "size": 8, "line": {"color": "white", "width": 1.2}},
                "error": {"width": 4.0, "thickness": 1.2, "color": color},
            },
        )
        # 幂律拟合虚线（在数据范围外各延伸一点，视觉上更像"拟合线"）
        rx = np.array([1.35, 11.0])
        fig.add_data(f"fit_x_{i}", rx, unit="μm", role="coord")
        fig.add_data(f"fit_y_{i}", coeff * rx ** -3.0, unit="rad2/s", role="series")
        fig.add_plot("line", data={"x": f"fit_x_{i}", "y": f"fit_y_{i}"}, legend=False,
                     style={"color": color, "dash": "dash", "width": 1.6})

    # ---- 主图：双对数 + 内侧镜像刻度 + 次刻度 ----
    fig.set_view(
        0,
        xlabel="R$_G$ (μm)",
        ylabel="$D_{eff}^{\\theta}$ (rad$^2$ s$^{-1}$)",
        xscale="log",
        yscale="log",
        grid=False,
        xlim=[1.3, 11.0],
        ylim=[3.0e-5, 1.4e-1],
        ticks={"inside": True, "mirror": True, "minor": True},
        loglabels="plain-x",
    )

    # ---- 内嵌子图：⟨Δθ²⟩ vs Δt（三组斜率） ----
    fig.add_inset(subplot=1, parent=0, rect=(0.575, 0.60, 0.405, 0.365),
                  fonts={"axis": 9, "tick": 8, "annotation": 8})
    dt = np.linspace(0, 5, 6)
    fig.add_data("dt", dt, unit="s", role="coord")
    for i, slope in enumerate((0.0165, 0.0090, 0.0032)):
        msd = slope * dt
        fig.add_data(f"msd_{i}", msd, unit="rad2", role="series")
        fig.add_data(f"msd_err_{i}", msd * 0.08 + 8e-5, unit="rad2", role="series")
        fig.add_plot(
            "scatter",
            data={"x": "dt", "y": f"msd_{i}", "error_y": f"msd_err_{i}"},
            subplot=1,
            legend=False,
            style={
                "color": SERIES[i + 1][1],
                "marker": {"symbol": "circle", "size": 4.5},
                "error": {"width": 2.0, "thickness": 1.0, "color": SERIES[i + 1][1]},
            },
        )
    fig.set_view(
        1,
        xlabel="Δt (s)",
        ylabel="$\\langle\\Delta\\theta^2\\rangle$ (rad$^2$)",
        grid=False,
        xlim=[-0.3, 5.4],
        ticks={"inside": True, "mirror": True, "minor": False},
    )

    # ---- 装饰：斜率 −3 参考三角 + ρ_B 箭头 ----
    fig.add_shape("triangle", subplot=0, anchor=(1.40, 3.0e-4), decades=0.26,
                  slope=-3, text="−3", color="#1a1a1a", width=1.2)
    fig.add_shape("arrow", subplot=0, start=(2.62, 6.0e-4), end=(2.62, 8.0e-2),
                  text="ρ$_B$", color="#4b6b8a", width=1.8)
    return fig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--serve", action="store_true", help="起浏览器交互页（默认只出 PNG）")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--out", default="docs/paper_panel_b.png")
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    fig = build()
    out = Path(__file__).resolve().parents[1] / args.out
    fig.savefig(out, dpi=args.dpi)
    print(f"saved {out}  ({out.stat().st_size / 1024:.0f} KB)")
    if args.serve:
        fig.show(sink="browser", port=args.port)


if __name__ == "__main__":
    main()
