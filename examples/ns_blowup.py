"""纳维–斯托克斯方程的有限时间爆破：非定常 Burgers 涡管的三维矢量动画。

## 这是一个真解，不是"画个爆炸"

取轴对称速度场

    u_r = -a(t) r / 2,      u_θ = Γ/(2πr) · [1 - exp(-r²/(2δ(t)²))],      u_z = a(t) z

其中应变率 `a(t) = a0 / (1 - t/T)` 随时间发散，涡核半径 `δ(t)` 满足

    d(δ²)/dt = 2ν - a(t)·δ²

这一族是**不可压 Navier–Stokes 方程的精确解**（非定常 Burgers 涡）：
`u_r`/`u_z` 是线性场，黏性项 `ν∇²u` 对它恒为零；`u_θ` 代进 θ 方向动量方程，
恰好化简成上面那个 `δ²` 的常微分方程。代入 `a(t) = a0/(1-t/T)`（取 `a0·T = 1`）可得闭式解

    δ²(t) = (1 - t/T) · [δ0² - 2νT·ln(1 - t/T)]

于是 `t → T` 时 `δ² → 0⁺`，涡量峰值

    ω_max = Γ / (2π δ²)  ~  1 / (T - t)

**在有限时间内发散**。速度 `u_θ ~ δ^{-1/2}` 也发散，所以这是"解本身在 T 时刻不存在了"
的经典爆破，而不是某个数值格式发散。

要说明的是：这一族在 z 方向无界（`u_z = a z`），总动能无穷，所以它**不构成**
千禧年问题里"有限能量解是否整体光滑"的反例——那是另一个问题。这里展示的是
NS 方程确实允许有限时间奇点这一事实本身。

## 动画内容

三维矢量场（箭头 = 速度，颜色 = 涡量大小），60 帧从 `t = 0` 走到 `t = 0.97T`：
涡管被轴向拉伸 → 半径收缩 → 旋转加快 → 涡量颜色烧穿色标上限。

用法：
    PYTHONPATH=src python examples/ns_blowup.py            # 全量（约 30–60 s）
    PYTHONPATH=src python examples/ns_blowup.py --quick    # 24 帧，约 10 s
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np

import plotkit as pk

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "ns_blowup"

# ---- 物理参数 -------------------------------------------------------------
T_BLOW = 1.0          # 爆破时刻
A0 = 1.0              # 应变率幅值（取 a0·T = 1，闭式解才干净）
DELTA0 = 0.25         # 初始涡核半径
GAMMA = 1.0           # 环量
NU = 1.0e-5           # 运动黏度（只影响对数项，量级上无关紧要）


def strain_rate(t: np.ndarray | float):
    """a(t) = a0 / (1 - t/T)：应变率在 T 时刻发散。"""
    return A0 / np.maximum(1.0 - np.asarray(t) / T_BLOW, 1e-9)


def core_radius_sq(t: np.ndarray | float):
    """δ²(t) = (1-t/T)·[δ0² - 2νT·ln(1-t/T)]，闭式解。"""
    s = np.maximum(1.0 - np.asarray(t) / T_BLOW, 1e-9)
    return s * (DELTA0**2 - 2.0 * NU * T_BLOW * np.log(s))


def velocity(x, y, z, t):
    """非定常 Burgers 涡的速度场（柱坐标换到直角坐标）。"""
    a = float(strain_rate(t))
    d2 = float(core_radius_sq(t))
    r = np.hypot(x, y)
    safe_r = np.maximum(r, 1e-9)
    u_theta = GAMMA / (2.0 * math.pi * safe_r) * (1.0 - np.exp(-r**2 / (2.0 * d2)))
    u_r = -0.5 * a * r
    # 柱 → 直角：u = u_r·r̂ + u_θ·θ̂
    ur_x, ur_y = u_r * x / safe_r, u_r * y / safe_r
    ut_x, ut_y = -u_theta * y / safe_r, u_theta * x / safe_r
    ux, uy = ur_x + ut_x, ur_y + ut_y
    uz = a * z
    return ux, uy, uz


def vorticity(x, y, z, t):
    """ω = (1/r)∂(r u_θ)/∂r · ẑ = Γ/(2πδ²)·exp(-r²/(2δ²))·ẑ。"""
    d2 = float(core_radius_sq(t))
    r = np.hypot(x, y)
    wz = GAMMA / (2.0 * math.pi * d2) * np.exp(-r**2 / (2.0 * d2))
    return np.zeros_like(wz), np.zeros_like(wz), wz


def sample_points(n_theta: int = 12, n_r: int = 4, n_z: int = 6, t: float = 0.0):
    """在一个随涡核收缩的柱体内取采样点：涡管越细，采样越密。"""
    # 采样盒**固定**（不随涡核收缩），否则每帧都把细管填满画面，看不出"变细"这件事
    r_max = 0.50
    z_max = 0.30
    theta = np.linspace(0.0, 2.0 * math.pi, n_theta, endpoint=False)
    radii = np.geomspace(0.012, r_max, n_r)   # 近轴加密：涡核越细越要采到
    zs = np.linspace(-z_max, z_max, n_z)
    TH, RR, ZZ = np.meshgrid(theta, radii, zs, indexing="ij")
    return RR * np.cos(TH), RR * np.sin(TH), ZZ


def frame_arrays(t: float, *, n_theta=12, n_r=4, n_z=6, arrow_len=0.055):
    """采样一帧。箭头长度按帧内最大速度归一化——方向与相对大小是真的，
    绝对量级交给颜色（涡量）和标题里的数字，否则 a(t)→∞ 会把箭头甩出画面。"""
    x, y, z = sample_points(n_theta, n_r, n_z, t)
    ux, uy, uz = velocity(x, y, z, t)
    _, _, wz = vorticity(x, y, z, t)
    speed = np.sqrt(ux**2 + uy**2 + uz**2)
    peak = float(speed.max()) or 1.0
    k = arrow_len / peak
    return (x.ravel(), y.ravel(), z.ravel(),
            (ux * k).ravel(), (uy * k).ravel(), (uz * k).ravel(),
            np.abs(wz).ravel(), speed.ravel())


def figure_for_frame(t: float, *, omega_cap: float):
    """一帧 = 一张 PlotKit 图：quiver3d（速度箭头）+ scatter3d（按涡量着色）。"""
    x, y, z, ux, uy, uz, omega, speed = frame_arrays(t)
    title = (f"t/T = {t / T_BLOW:0.3f}   |u|max = {speed.max():8.2f}   "
             f"omega_max = {omega.max():8.2f}")

    fig = pk.figure(size=(6.4, 5.0), dpi=110, title=title)
    fig.add_data("px", x, role="auto")
    fig.add_data("py", y, role="auto")
    fig.add_data("pz", z, role="auto")
    fig.add_data("ux", ux, role="auto")
    fig.add_data("uy", uy, role="auto")
    fig.add_data("uz", uz, role="auto")
    fig.add_data("om", omega, role="auto")

    fig.add("quiver3d", {"x": "px", "y": "py", "z": "pz",
                         "u": "ux", "v": "uy", "w": "uz"},
            style={"color": "#38bdf8", "width": 1.0, "length": 0.05})
    fig.add("scatter3d", {"x": "px", "y": "py", "z": "pz", "scalar": "om"},
            style={"cmap": "inferno", "marker": {"size": 2.5}, "clim": [0.0, omega_cap]})
    fig.set_view(0, elev=16, azim=-62, zoom=0.72)
    return fig


def omega_peak(t: float) -> float:
    return GAMMA / (2.0 * math.pi * float(core_radius_sq(t)))


def charts_timeseries(times: np.ndarray) -> dict:
    """二维：涡量峰值与涡核半径随 (T - t) 的发散（双对数）。"""
    order = np.argsort(T_BLOW - times)          # 按 T-t 递增排：曲线从左（临近爆破）读向右
    gap = (T_BLOW - times)[order]
    fig = pk.figure(size=(7.0, 4.4), dpi=120)
    fig.add_data("gap", gap, role="coord")
    fig.add_data("wmax", np.array([omega_peak(t) for t in times])[order], role="series")
    fig.add_data("delta", np.array([math.sqrt(max(float(core_radius_sq(t)), 1e-12))
                                    for t in times])[order], role="series")
    fig.add_plot("line", x="gap", y="wmax",
                 style={"color": "#f97316", "width": 2.2, "marker": {"symbol": None}},
                 label="ω_max ∝ (T-t)⁻¹")
    fig.add_plot("line", x="gap", y="delta",
                 style={"color": "#38bdf8", "width": 2.2, "marker": {"symbol": None}},
                 label="δ ∝ (T-t)^(1/2)")
    fig.set_view(0, xscale="log", yscale="log", xlabel="T - t  (s)",
                 ylabel="ω_max (1/s)  /  δ (m)", grid=True, legend=True)
    path = OUT_DIR / "01_blowup_law.png"
    fig.savefig(path, dpi=120)
    return {"path": path}


def make_gif(frames: list[bytes], path: Path, fps: int = 15) -> int:
    import io

    from PIL import Image

    images = [Image.open(io.BytesIO(b)).convert("P", palette=Image.ADAPTIVE, colors=128)
              for b in frames]
    images[0].save(path, save_all=True, append_images=images[1:],
                   duration=int(1000 / fps), loop=0, optimize=True)
    return path.stat().st_size


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NS 方程爆破解的三维矢量动画")
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--fps", type=int, default=15)
    parser.add_argument("--quick", action="store_true", help="24 帧 + 小画布")
    args = parser.parse_args(argv)

    frames_n = 24 if args.quick else args.frames
    size = (420, 340) if args.quick else (640, 500)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # 采样到 0.97T：再往前涡管细到网格分辨不出，动画会闪
    times = np.linspace(0.0, 0.97 * T_BLOW, frames_n)
    omega_cap = omega_peak(0.0) * 8.0     # 固定色标上限，颜色变化才是"同一把尺子"

    print(f"[1/3] 渲染 {frames_n} 帧三维矢量场 …", flush=True)
    frames: list[bytes] = []
    for i, t in enumerate(times):
        fig = figure_for_frame(float(t), omega_cap=omega_cap)
        frames.append(fig.render(width=size[0], height=size[1], backend="pyvista", fmt="png"))
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  frame {i + 1}/{frames_n}  t={t:.3f}  ω_max={omega_peak(t):8.2f}",
                  flush=True)

    gif = OUT_DIR / "02_ns_blowup_3d.gif"
    size_bytes = make_gif(frames, gif, fps=args.fps)
    print(f"[2/3] GIF {gif.name}  {size_bytes / 1024:.0f} KB", flush=True)

    print("[3/3] 二维爆破律 + 末帧矢量图 …", flush=True)
    series = charts_timeseries(times)
    last = figure_for_frame(float(times[-1]), omega_cap=omega_cap)
    svg_path = OUT_DIR / "03_last_frame.svg"
    svg_path.write_bytes(last.render(width=size[0], height=size[1], backend="pyvista",
                                     fmt="svg"))

    # 末帧位图另存，方便直接看
    (OUT_DIR / "04_last_frame.png").write_bytes(frames[-1])

    summary = {
        "frames": frames_n,
        "gif_kb": round(size_bytes / 1024, 1),
        "omega0": round(omega_peak(0.0), 3),
        "omega_end": round(omega_peak(float(times[-1])), 3),
        "delta0": round(math.sqrt(float(core_radius_sq(0.0))), 4),
        "delta_end": round(math.sqrt(float(core_radius_sq(float(times[-1])))), 4),
        "series": str(series["path"].name),
    }
    print(summary, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
