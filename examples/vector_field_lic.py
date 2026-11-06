"""把矢量场画到"论文插图"级别：LIC 纹理切片 + 体渲染三维涡管。

两件事对应两种技法：

1. **二维切片 → 线积分卷积（LIC）**。普通 `quiver` 只能抽几十根箭头，稠密的涡与剪切层
   全被抽掉；LIC 让白噪声沿流线糊开，纹理走向就是流线，于是既稠密又连续。PlotKit 里
   是一个新图层 `lic`：给 `u/v`（二维场），它自己算纹理并上色。
2. **三维 → 体渲染（volume）**。表面等值面只能看到"壳"，涡管内部结构看不见；
   `add_volume` 用 RGB 传递函数把标量场画成半透明的发光体。PlotKit 里是 `volume` 图层
   （仅 pyvista 后端）。

用法：
    PYTHONPATH=src python examples/vector_field_lic.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

import matplotlib
from matplotlib.colors import LinearSegmentedColormap

import plotkit as pk

OUT = Path(__file__).resolve().parent.parent / "docs" / "vector_field"

BG = "#04070d"

# 参考图那种"深蓝底 + 青白丝"的配色，注册成命名 colormap 后直接按名字用
if "lic-blue" not in matplotlib.colormaps:
    matplotlib.colormaps.register(
        LinearSegmentedColormap.from_list(
            "lic-blue", ["#03080f", "#0a2237", "#155a86", "#4fb0d8", "#dff4ff"]
        )
    )


def two_vortex_field(n: int = 420):
    """两个反向旋转的涡 + 均匀来流 + 一点剪切，用来演示纹理怎么"抱住"涡。"""
    x = np.linspace(-1.0, 1.0, n)
    y = np.linspace(-1.0, 1.0, n)
    X, Y = np.meshgrid(x, y)
    r1 = np.hypot(X - 0.34, Y + 0.16)
    r2 = np.hypot(X + 0.42, Y - 0.30)
    u = (
        -(Y + 0.16) / (r1**2 + 0.035) * 0.105
        + (Y - 0.30) / (r2**2 + 0.06) * 0.085
        + 0.10 * (1.0 - Y**2)
    )
    v = (
        (X - 0.34) / (r1**2 + 0.035) * 0.105
        - (X + 0.42) / (r2**2 + 0.06) * 0.085
        + 0.06 * X * Y
    )
    return x, y, u, v


def chart_lic_slice() -> Path:
    """参考图 1 的复刻：暗底 + 蓝调 + 沿流线拉丝的纹理。"""
    x, y, u, v = two_vortex_field(460)
    fig = pk.figure(size=(6.6, 6.6), dpi=130, theme="netlab-dark", title=None)
    fig.spec["figure"].update(
        {
            "facecolor": BG,
            "axes_facecolor": BG,
            "textcolor": "#cbd5e1",
            "gridcolor": "#111827",
        }
    )
    fig.add_data("x", x)
    fig.add_data("y", y)
    fig.add_data("u", u)
    fig.add_data("v", v)
    fig.add(
        "lic",
        {"x": "x", "y": "y", "u": "u", "v": "v"},
        style={"cmap": "lic-blue", "steps": 22, "step_px": 2.0, "contrast": 2.0},
    )
    fig.set_view(0, xlabel="x", ylabel="y", grid=False)
    path = OUT / "01_lic_slice.png"
    fig.savefig(path, dpi=130)
    return path


def burgers_vorticity(n: int = 96, nz: int = 72):
    """Burgers 涡的涡量场 ω_z = Γ/(2πδ²)·exp(-r²/2δ²)，做成 (nz, ny, nx) 的体数据。"""
    delta = 0.17
    x = np.linspace(-1.0, 1.0, n)
    y = np.linspace(-1.0, 1.0, n)
    z = np.linspace(-0.95, 0.95, nz)
    X, Y = np.meshgrid(x, y, indexing="xy")
    core = np.exp(-(X**2 + Y**2) / (2.0 * delta**2))  # (ny, nx)
    shape_z = np.exp(-((z / 0.9) ** 2))[:, None, None]  # 两端渐隐
    values = core[None, :, :] * shape_z  # (nz, ny, nx)
    return x, y, z, values


def ring_particles(delta: float = 0.17, rings: int = 9, per_ring: int = 64):
    """涡核外的粒子环：参考图里那些"发光的环"，用来把三维形状讲清楚。"""
    zs = np.linspace(-0.85, 0.85, rings)
    theta = np.linspace(0.0, 2.0 * np.pi, per_ring, endpoint=False)
    pts = []
    for z in zs:
        taper = 1.0 + 0.55 * (z / 0.85) ** 2  # 中段细、两端略张开
        r = 1.35 * delta * taper
        pts.append(
            np.column_stack(
                [r * np.cos(theta), r * np.sin(theta), np.full_like(theta, z)]
            )
        )
    return np.vstack(pts)


def chart_volume() -> Path:
    """参考图 2 的复刻：半透明发光涡管 + 粒子环。"""
    x, y, z, values = burgers_vorticity()
    fig = pk.figure(size=(5.4, 6.4), dpi=130, theme="netlab-dark")
    fig.spec["figure"].update(
        {
            "facecolor": BG,
            "axes_facecolor": BG,
            "textcolor": "#cbd5e1",
            "gridcolor": "#111827",
        }
    )
    fig.add_data("x", x)
    fig.add_data("y", y)
    fig.add_data("z", z)
    fig.add_data("w", values)

    fig.add(
        "volume",
        {"x": "x", "y": "y", "z": "z", "values": "w"},
        style={
            "cmap": "inferno",
            "shade": True,
            "opacity_ramp": [0.0, 0.0, 0.01, 0.06, 0.18, 0.42, 0.80],
            "clim": [0.0, 1.0],
        },
    )

    pts = ring_particles()
    speed = np.hypot(pts[:, 0], pts[:, 1])  # 环上速度近似随半径变
    fig.add_data("px", pts[:, 0])
    fig.add_data("py", pts[:, 1])
    fig.add_data("pz", pts[:, 2])
    fig.add_data("ps", speed)
    fig.add(
        "scatter3d",
        {"x": "px", "y": "py", "z": "pz", "scalar": "ps"},
        style={"cmap": "cool", "marker": {"size": 4}, "opacity": 0.9},
    )
    fig.set_view(0, elev=10, azim=-72, zoom=1.05)
    path = OUT / "02_volume_3d.png"
    path.write_bytes(fig.render(width=700, height=840, backend="pyvista", fmt="png"))
    return path


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    p1 = chart_lic_slice()
    print(f"[1/2] {p1.name}  {p1.stat().st_size / 1024:.0f} KB", flush=True)
    p2 = chart_volume()
    print(f"[2/2] {p2.name}  {p2.stat().st_size / 1024:.0f} KB", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
