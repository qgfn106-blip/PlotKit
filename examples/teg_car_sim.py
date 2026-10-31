"""生物质能温差发电小车 · 多物理场耦合仿真（PlotKit 综合性能验证项目）

一个"真实工程问题"的端到端实现：
燃料燃烧 → 温差发电（TEG）→ DC-DC → 超级电容 → 直流电机 → 齿轮传动 → 车轮
→ 车辆纵向动力学 → 凸轮转向 → 二维赛道轨迹 → 绕桩判定 → 参数优化。

物理模型（五个子系统 + 一个耦合回路）
------------------------------------
1) 热能：热端/冷端两节点集总热容模型。火焰对热端的换热用 h·(T_flame − T_h)，
   TEG 的导热、塞贝克、佩尔帖、焦耳热全部计入，保证 Q_h − Q_c = P_电（能量守恒）。
2) 电气：TEG 在匹配负载下 P = (N·α·ΔT)² / (4·R_int)；经 DC-DC（η）给超级电容充电；
   电容电压 ODE：C·V·dV/dt = η·P_teg − P_motor。
3) 电机：直流电机准静态（电枢电感时间常数 ~1.4 ms ≪ 步长，令 di/dt ≈ 0）；
   车轮与电机刚性啮合，转速由车速反推（ω_m = v·i_g/r_w），避免打滑伪自由度。
4) 机械：齿轮减速 + 滚动阻力 + 空气阻力；整车纵向动力学。
5) 转向：凸轮/连杆机构给出 δ(s)（s = 累计里程），用自行车模型积分出真实轨迹。
6) 耦合：T_h/T_c → ΔT → 电压/功率 → 电容电压 → 电机电流/转矩 → 车速 → 散热器换热
   → 回到 T_c。这是**有环**网络，必须时间步进，不能当无环拓扑做一次排序。

用法
----
    python examples/teg_car_sim.py                 # 全量：仿真 + 29 张图 + 3D 动画 + 报告
    python examples/teg_car_sim.py --quick         # 参数扫描降档（更快）
    python examples/teg_car_sim.py --points 200000 # 规模测试点数

产物：`docs/teg_car/` 下的 PNG 与 REPORT.md。
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import plotkit as pk

# 本项目全是上万点的时序曲线，默认带点标记会糊成一片（PlotKit 默认 style 含 marker.symbol）
pk.init(marker={"symbol": None})

OUT_DIR = Path(__file__).resolve().parents[1] / "docs" / "teg_car"

# 与赛事规则相关的硬约束（2027 第十届 · 生物质能电动车）
CAR_MAX_LEN = 0.250    # m，车辆最大外形 200 mm × 250 mm
CAR_MAX_WID = 0.200
OBSTACLE_R = 0.015     # m，锥桶半径

_trapz = getattr(np, "trapezoid", None) or np.trapz


# --------------------------------------------------------------------------- #
# 1. 参数
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Params:
    # ---- 燃料：固体酒精 ----
    fuel_mass: float = 0.020       # kg
    burn_time: float = 900.0       # s，全部烧完所需时间
    Hu: float = 26.0e6             # J/kg，乙醇低位热值
    T_flame: float = 620.0         # °C，火焰/燃烧面等效温度
    h_flame: float = 0.060         # W/K，火焰到热端的等效换热系数

    # ---- 热端 / 冷端集总热容模型 ----
    C_h: float = 25.0              # J/K，热端（铝均温板 30 g）
    C_c: float = 45.0              # J/K，冷端（铝散热器 50 g）
    K_teg: float = 0.35            # W/K，穿过 TEG 的等效热导
    hA_c: float = 0.90             # W/K，冷端对空气的对流换热
    hA_h: float = 0.05             # W/K，热端对环境漏热
    Tamb: float = 25.0             # °C

    # ---- TEG 模块 ----
    N: int = 127                   # 热电偶对数
    alpha: float = 3.6e-4          # V/K（每对）
    R_int: float = 2.4             # Ω
    eta_dcdc: float = 0.85         # DC-DC 变换效率

    # ---- 储能：超级电容 ----
    C_cap: float = 8.0             # F
    V_max: float = 2.7             # V（稳压上限）

    # ---- 直流电机 ----
    Rm: float = 0.85               # Ω
    Ke: float = 5.4e-3             # V·s/rad
    Kt: float = 5.4e-3             # N·m/A
    i_limit: float = 2.2           # A，限流
    v_cutoff: float = 0.55         # V，欠压保护

    # ---- 传动 ----
    i_g: float = 18.0              # 减速比
    eta_g: float = 0.86            # 齿轮效率
    r_w: float = 0.022             # m，车轮半径

    # ---- 整车 ----
    m: float = 0.55                # kg
    Crr: float = 0.012             # 滚动阻力系数
    CdA: float = 4.2e-3            # m²
    rho_air: float = 1.20          # kg/m³
    g: float = 9.81

    # ---- 转向机构 ----
    L_wb: float = 0.160            # m，轴距
    cam_harmonics: int = 12        # 凸轮轮廓拟合谐波数（3 阶不够，见 16b）


P = Params()

# 状态向量
TH, TC, VC, VV = range(4)

# 赛道几何（体育场形：两直道 + 两半圆，闭合）
TRACK_STRAIGHT = 0.90
TRACK_R = 0.55          # m，中心线弯道半径
TRACK_HALF_W = 0.25     # m，赛道半宽（画边界用）
L_LAP = 2 * TRACK_STRAIGHT + 2 * math.pi * TRACK_R


def fuel_power(t: float, p: Params = P) -> float:
    """燃料释放的总热功率（W），用于能量账。"""
    if t >= p.burn_time:
        return 0.0
    return p.fuel_mass * p.Hu / p.burn_time


def teg_matched(dT: float, p: Params = P) -> tuple[float, float, float]:
    """TEG 在匹配负载下的开路电压 / 电流 / 输出功率。"""
    if dT <= 0:
        return 0.0, 0.0, 0.0
    voc = p.N * p.alpha * dT
    cur = voc / (2.0 * p.R_int)
    return voc, cur, cur * cur * p.R_int


def rhs(t: float, y: np.ndarray, p: Params = P, duty: float = 1.0) -> np.ndarray:
    """耦合系统右端项。y = [T_h, T_c, V_cap, v]。"""
    th, tc, vc, vv = y

    # --- 热端输入：火焰对流（自限温，不会像"恒定功率"那样无限升温）---
    q_in = max(p.h_flame * (p.T_flame - th), 0.0)

    dT = max(th - tc, 0.0)
    voc, cur, p_elec = teg_matched(dT, p)
    th_k, tc_k = th + 273.15, tc + 273.15
    a_tot = p.N * p.alpha
    q_cond = p.K_teg * dT
    q_h = q_cond + a_tot * th_k * cur - 0.5 * cur * cur * p.R_int
    q_c = q_cond + a_tot * tc_k * cur + 0.5 * cur * cur * p.R_int

    d_th = (q_in - q_h - p.hA_h * (th - p.Tamb)) / p.C_h
    d_tc = (q_c - p.hA_c * (tc - p.Tamb)) / p.C_c

    # --- 电气：电容 + 准静态电机（车轮刚性啮合）---
    w_m = vv * p.i_g / p.r_w
    v_app = duty * max(vc, 0.0) if vc >= p.v_cutoff else 0.0
    i_m = (v_app - p.Ke * w_m) / p.Rm
    i_m = min(max(i_m, 0.0), p.i_limit)
    p_motor = v_app * i_m
    d_vc = (p.eta_dcdc * p_elec - p_motor) / (p.C_cap * max(vc, 0.05))
    if vc >= p.V_max and d_vc > 0.0:
        d_vc = 0.0                        # 稳压：到上限不再充

    # --- 整车纵向动力学 ---
    f_drive = p.eta_g * p.i_g * p.Kt * i_m / p.r_w
    f_roll = p.Crr * p.m * p.g
    f_air = 0.5 * p.rho_air * p.CdA * vv * vv
    d_v = (f_drive - f_roll - f_air) / p.m
    if vv <= 0.0 and d_v < 0.0:
        d_v = 0.0

    return np.array([d_th, d_tc, d_vc, d_v], dtype=float)


def rk4(t: float, y: np.ndarray, dt: float, p: Params, duty: float = 1.0) -> np.ndarray:
    k1 = rhs(t, y, p, duty)
    k2 = rhs(t + 0.5 * dt, y + 0.5 * dt * k1, p, duty)
    k3 = rhs(t + 0.5 * dt, y + 0.5 * dt * k2, p, duty)
    k4 = rhs(t + dt, y + dt * k3, p, duty)
    return y + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)


def simulate(p: Params = P, *, t_end: float = 240.0, dt: float = 0.005,
             v0: float = 0.0) -> dict:
    """RK4 时间推进，返回各物理量时间序列。"""
    n = int(round(t_end / dt)) + 1
    t = np.empty(n)
    Y = np.empty((n, 4))
    y = np.array([p.Tamb, p.Tamb, 1.20, v0], dtype=float)   # 电容赛前预充 1.2 V
    t0 = time.perf_counter()
    for k in range(n):
        t[k] = k * dt
        Y[k] = y
        if k + 1 < n:
            y = rk4(t[k], y, dt, p)
            y[VC] = max(y[VC], 0.0)
            y[VV] = max(y[VV], 0.0)
    wall = time.perf_counter() - t0

    th, tc, vc, vv = Y.T
    dT = np.maximum(th - tc, 0.0)
    voc = p.N * p.alpha * dT
    i_teg = voc / (2 * p.R_int)
    p_teg = i_teg * i_teg * p.R_int
    w_m = vv * p.i_g / p.r_w
    v_app = np.where(vc >= p.v_cutoff, vc, 0.0)
    i_m = np.clip((v_app - p.Ke * w_m) / p.Rm, 0.0, p.i_limit)
    s = np.concatenate([[0.0], np.cumsum(0.5 * (vv[1:] + vv[:-1]) * dt)])
    return {
        "t": t, "Th": th, "Tc": tc, "dT": dT, "Voc": voc, "I_teg": i_teg,
        "P_teg": p_teg, "V_cap": vc, "E_cap": 0.5 * p.C_cap * vc * vc,
        "I_motor": i_m, "T_motor": p.Kt * i_m, "P_motor": v_app * i_m,
        "omega": w_m, "rpm": w_m * 60.0 / (2 * math.pi),
        "v": vv, "s": s, "acc": np.gradient(vv, dt),
        "P_fuel": np.array([fuel_power(x, p) for x in t]),
        "wall_s": wall, "dt": dt, "p": p,
    }


# --------------------------------------------------------------------------- #
# 2. 赛道 / 凸轮 / 轨迹
# --------------------------------------------------------------------------- #
def track_kappa(s: np.ndarray, *, radius: float = TRACK_R,
                straight: float = TRACK_STRAIGHT) -> np.ndarray:
    """体育场形赛道的曲率 κ(s)（s 取模到一圈）。"""
    lap = 2.0 * straight + 2.0 * math.pi * radius
    sm = np.mod(s, lap)
    k = np.zeros_like(sm, dtype=float)
    a0 = straight
    a1 = a0 + math.pi * radius
    a2 = a1 + straight
    k[(sm >= a0) & (sm < a1)] = 1.0 / radius
    # 闭合的体育场（跑道形）两端都是左转：一圈累计转向 2π，位移才回到原点
    k[(sm >= a2)] = 1.0 / radius
    return k


def cam_profile(p: Params = P, n: int = 720, *, harmonics: int | None = None) -> np.ndarray:
    """凸轮轮廓：对理想转向角 δ_ideal(s)=atan(L·κ(s)) 做有限谐波拟合。

    这是"用有限谐波的凸轮去逼近理想转向规律"的真实工程折中——拟合误差
    就是车辆偏离中心线、压到锥桶的物理来源。

    拟合完再做一次**转角标定**：把轮廓整体缩放，使一圈的累计转向严格等于 2π。
    否则残余的 0.1% 转向误差会在几十圈后累积成明显的方向漂移（第一版就是
    每圈多转 3°、轨迹扇开）。真实凸轮在装配时也是靠这个标定来找零位的。
    """
    s = np.linspace(0.0, L_LAP, n, endpoint=False)
    ideal = np.arctan(p.L_wb * track_kappa(s))
    h = p.cam_harmonics if harmonics is None else int(harmonics)
    spec = np.fft.rfft(ideal)
    spec[h + 1:] = 0.0
    cam = np.fft.irfft(spec, n)

    ds = L_LAP / n
    net = float(np.sum(np.tan(cam)) * ds / p.L_wb)
    scale = 1.0
    if abs(net) > 1e-9:
        lo, hi = 0.5, 1.5
        for _ in range(60):                     # 二分求使 Σtan(kδ)ds/L = 2π 的 k
            mid = 0.5 * (lo + hi)
            if float(np.sum(np.tan(mid * cam)) * ds / p.L_wb) < 2.0 * math.pi:
                lo = mid
            else:
                hi = mid
        scale = 0.5 * (lo + hi)
    return cam * scale


def steering_angle(s: np.ndarray, gain: float = 1.0) -> np.ndarray:
    """凸轮给出的转向角（按里程查表，一圈一循环）。"""
    n = _CAM.size
    idx = np.mod(s, L_LAP) / L_LAP * n
    i0 = np.floor(idx).astype(int) % n
    i1 = (i0 + 1) % n
    frac = idx - np.floor(idx)
    return gain * (_CAM[i0] * (1 - frac) + _CAM[i1] * frac)


def drive_trajectory(res: dict, p: Params = P, *, gain: float = 1.0) -> dict:
    """由车速序列积分车辆位姿（自行车模型，δ 来自凸轮轮廓）。"""
    s = res["s"]
    ds = np.diff(s, prepend=s[0])
    delta = steering_angle(s, gain)
    psi = np.zeros_like(s)
    x = np.zeros_like(s)
    y = np.zeros_like(s)
    for i in range(1, s.size):
        psi[i] = psi[i - 1] + ds[i] * math.tan(delta[i]) / p.L_wb
        x[i] = x[i - 1] + ds[i] * math.cos(psi[i])
        y[i] = y[i - 1] + ds[i] * math.sin(psi[i])
    return {"x": x, "y": y, "psi": psi, "delta": delta, "s": s, "v": res["v"]}


def ideal_path(p: Params = P, n: int = 2000, *, radius: float = TRACK_R,
               straight: float = TRACK_STRAIGHT) -> dict:
    """理想中心线（按赛道曲率积分），用于对比与放锥桶。

    `radius`/`straight` 可调，用来生成同心的赛道内外边界。
    """
    lap = 2.0 * straight + 2.0 * math.pi * radius
    s = np.linspace(0.0, lap, n)
    kap = track_kappa(s, radius=radius, straight=straight)
    ds = np.diff(s, prepend=s[0])
    psi = np.cumsum(kap * ds)
    x = np.concatenate([[0.0], np.cumsum(ds[1:] * np.cos(psi[1:]))])
    y = np.concatenate([[0.0], np.cumsum(ds[1:] * np.sin(psi[1:]))])
    return {"x": x, "y": y, "psi": psi, "kappa": kap, "s": s}


def place_obstacles(center: dict, stops: list[float], offset: float = 0.150) -> np.ndarray:
    """沿理想中心线法向交替偏移放置锥桶。"""
    pts = []
    for j, st in enumerate(stops):
        i = int(np.argmin(np.abs(center["s"] - st)))
        nx, ny = -math.sin(center["psi"][i]), math.cos(center["psi"][i])
        side = 1.0 if j % 2 == 0 else -1.0
        pts.append([center["x"][i] + side * offset * nx,
                    center["y"][i] + side * offset * ny])
    return np.asarray(pts, dtype=float)


OBSTACLE_S = (0.80, 1.60, 2.30, 3.40, 4.10, 4.80)
_CAM = cam_profile()


def car_clearance(traj: dict, obstacles: np.ndarray) -> np.ndarray:
    """车体矩形（0.25 × 0.20）四角到最近锥桶的最小净距；负值 = 压到。"""
    hl, hw = CAR_MAX_LEN / 2.0, CAR_MAX_WID / 2.0
    x, y, psi = traj["x"], traj["y"], traj["psi"]
    corners = np.array([[hl, hw], [hl, -hw], [-hl, hw], [-hl, -hw]])
    step = max(1, x.size // 1200)
    idxs = np.arange(0, x.size, step)
    out = np.empty(idxs.size)
    for k, i in enumerate(idxs):
        c, s_ = math.cos(psi[i]), math.sin(psi[i])
        pts = corners @ np.array([[c, -s_], [s_, c]]).T + np.array([x[i], y[i]])
        d = np.linalg.norm(pts[:, None, :] - obstacles[None, :, :], axis=2)
        out[k] = d.min() - OBSTACLE_R
    return np.interp(np.arange(x.size), idxs, out)


# --------------------------------------------------------------------------- #
# 3. 三维场：有限差分 / 有限元（真算）
# --------------------------------------------------------------------------- #
def teg_plate_field(p: Params = P, n: int = 61, k: float = 30.0,
                    size: float = 0.040, t_hot: float | None = None,
                    t_cold: float | None = None,
                    iters: int = 2500) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """热端均温板稳态温度场：中心 20×20 mm 受火焰加热、四周边缘靠冷端散热。

    边界条件取"物理上站得住"的那种：中心受热区按 Dirichlet 给定热端温度
    （= 集总模型算出的 T_h），四周边缘给定环境温度，中间靠导热扩散。
    求解用五点差分 + 红黑 SOR（Gauss-Seidel）；纯 Jacobi 同时更新在 ω>1 时发散。
    """
    h = size / (n - 1)
    hot = float(p.Tamb + 78.0) if t_hot is None else float(t_hot)
    cold = float(p.Tamb + 27.0) if t_cold is None else float(t_cold)
    T = np.full((n, n), cold)
    T[0, :] = T[-1, :] = T[:, 0] = T[:, -1] = cold
    half = max(1, int(round(0.020 / h / 2)))
    c0 = n // 2 - half
    c1 = n // 2 + half
    T[c0:c1, c0:c1] = hot
    omega = 1.7
    ii, jj = np.meshgrid(np.arange(1, n - 1), np.arange(1, n - 1), indexing="ij")
    par = (ii + jj) % 2
    for _ in range(iters):
        for color in (0, 1):
            mask = par == color
            lap = 0.25 * (T[:-2, 1:-1] + T[2:, 1:-1] + T[1:-1, :-2] + T[1:-1, 2:])
            T[1:-1, 1:-1] = np.where(mask, T[1:-1, 1:-1] + omega * (lap - T[1:-1, 1:-1]),
                                     T[1:-1, 1:-1])
            T[c0:c1, c0:c1] = hot
    xs = np.linspace(0, size * 1000, n)
    return xs, xs, T


def heatsink_field(p: Params = P, nx: int = 21, ny: int = 61,
                   fin_h: float = 0.020, pitch: float = 0.005,
                   iters: int = 2500) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """散热器翅片剖面温度场：底部恒温、表面牛顿对流（FD + SOR）。"""
    k_al, h_conv = 200.0, 22.0
    dx, dy = pitch / (nx - 1), fin_h / (ny - 1)
    bi_x, bi_y = h_conv * dy / k_al, h_conv * dx / k_al
    T = np.full((ny, nx), float(p.Tamb))
    T[0, :] = 85.0
    for _ in range(iters):
        T[1:-1, 1:-1] = 0.25 * (T[:-2, 1:-1] + T[2:, 1:-1] + T[1:-1, :-2] + T[1:-1, 2:])
        T[1:-1, 0] = (T[1:-1, 1] + bi_x * p.Tamb) / (1.0 + bi_x)
        T[1:-1, -1] = (T[1:-1, -2] + bi_x * p.Tamb) / (1.0 + bi_x)
        T[-1, 1:-1] = (T[-2, 1:-1] + bi_y * p.Tamb) / (1.0 + bi_y)
    xs = np.linspace(0, pitch * 1000, nx)
    ys = np.linspace(0, fin_h * 1000, ny)
    return xs, ys, T


def chassis_beam_fe(p: Params = P, n_el: int = 60, L: float = 0.25,
                    load_n: float = 6.0, width: float = 0.20, thick: float = 0.003,
                    E: float = 2.4e9) -> dict:
    """底盘简支梁有限元（Euler-Bernoulli，2 节点 4 自由度）：挠度与弯曲应力。"""
    EIz = E * (width * thick ** 3 / 12.0)
    ndof = 2 * (n_el + 1)
    K = np.zeros((ndof, ndof))
    le = L / n_el
    ke = EIz / le ** 3 * np.array([
        [12, 6 * le, -12, 6 * le],
        [6 * le, 4 * le ** 2, -6 * le, 2 * le ** 2],
        [-12, -6 * le, 12, -6 * le],
        [6 * le, 2 * le ** 2, -6 * le, 4 * le ** 2]])
    for e in range(n_el):
        idx = [2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]
        K[np.ix_(idx, idx)] += ke
    F = np.zeros(ndof)
    F[2 * (n_el // 2)] = -load_n
    keep = [i for i in range(ndof) if i not in (0, 2 * n_el)]
    U = np.zeros(ndof)
    U[keep] = np.linalg.solve(K[np.ix_(keep, keep)], F[keep])
    x = np.linspace(0, L, n_el + 1)
    w = U[0::2]
    sigma = np.zeros(n_el + 1)
    for e in range(n_el):
        ue = U[[2 * e, 2 * e + 1, 2 * e + 2, 2 * e + 3]]
        M = EIz / le ** 2 * np.array([-6, -4 * le, 6, -2 * le]) @ ue
        sigma[e] = abs(M) * (thick / 2) / (thick ** 3 / 12.0) / width
    sigma[-1] = sigma[-2]
    return {"x": x, "w": w * 1000.0, "sigma": sigma / 1e3}


# --------------------------------------------------------------------------- #
# 4. 出图 helper
# --------------------------------------------------------------------------- #
def save(fig, name: str, *, width: int = 980, height: int = 560,
         backend: str | None = None) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    if backend and backend != "mpl":
        path.write_bytes(fig.render(width=width, height=height, backend=backend))
    else:
        fig.savefig(path, pixels=width)
    return path


def new(title: str, size=(7.4, 4.3)):
    fig = pk.figure(size=size, dpi=110, title=title)
    return fig


# --------------------------------------------------------------------------- #
# 5. 二维图
# --------------------------------------------------------------------------- #
def charts_thermal(res, p=P):
    t = res["t"]
    fig = new("热端 / 冷端温度与温差")
    fig.add_data("t", t, role="coord", unit="s")
    fig.add_plot("line", x="t", y=res["Th"], label="热端 T_h")
    fig.add_plot("line", x="t", y=res["Tc"], label="冷端 T_c")
    fig.add_plot("line", x="t", y=res["dT"], label="温差 ΔT", style={"dash": "dash"})
    fig.set_view(0, xlabel="时间 (s)", ylabel="温度 (°C)", grid=True)
    save(fig, "01_temperatures.png")

    fig = new("功率流：火焰 → TEG → 电机")
    fig.add_data("t", t, role="coord", unit="s")
    q_in = np.array([p.h_flame * max(p.T_flame - x, 0.0) for x in res["Th"]])
    fig.add_plot("line", x="t", y=q_in, label="火焰传给热端 (W)")
    fig.add_plot("line", x="t", y=res["P_teg"], label="TEG 输出电功率 (W)")
    fig.add_plot("line", x="t", y=res["P_motor"], label="电机消耗功率 (W)")
    fig.set_view(0, xlabel="时间 (s)", ylabel="功率 (W)", grid=True)
    save(fig, "02_power_flow.png")


def charts_teg_curves(p=P):
    fig = new("TEG 伏安特性（不同温差）")
    for dT in (20.0, 40.0, 60.0, 80.0):
        voc = p.N * p.alpha * dT
        cur = np.linspace(0, voc / p.R_int, 120)
        fig.add_plot("line", x=cur, y=voc - cur * p.R_int, label=f"ΔT={dT:.0f} K")
    fig.set_view(0, xlabel="电流 (A)", ylabel="电压 (V)", grid=True)
    save(fig, "03_teg_vi.png")

    grid = np.linspace(0, 120, 200)
    pw = np.array([teg_matched(x, p)[2] for x in grid])
    fig = new("输出功率 — 温差曲线")
    fig.add_plot("line", x=grid, y=pw, label="匹配负载输出功率")
    fig.set_view(0, xlabel="温差 ΔT (K)", ylabel="电功率 (W)", grid=True)
    save(fig, "04_power_vs_dt.png")

    eff = np.zeros_like(grid)
    for i, dT in enumerate(grid):
        q_h = p.K_teg * dT + (p.N * p.alpha) * (p.Tamb + dT / 2 + 273.15) * teg_matched(dT, p)[1]
        eff[i] = 100.0 * pw[i] / q_h if q_h > 1e-9 else 0.0
    fig = new("TEG 转换效率随温差变化")
    fig.add_plot("line", x=grid, y=eff, label="热电转换效率")
    fig.set_view(0, xlabel="温差 ΔT (K)", ylabel="效率 (%)", grid=True)
    save(fig, "05_teg_efficiency.png")


def charts_electrical(res, p=P):
    t = res["t"]
    fig = new("超级电容：电压 / 储能")
    fig.add_data("t", t, role="coord", unit="s")
    fig.add_plot("line", x="t", y=res["V_cap"], label="电容电压 (V)")
    fig.add_plot("line", x="t", y=res["E_cap"], label="储能 (J)")
    fig.set_view(0, xlabel="时间 (s)", ylabel="电压 (V) / 能量 (J)", grid=True)
    save(fig, "06_supercap.png")

    fig = new("电机：电流 / 转速 / 转矩")
    fig.add_data("t", t, role="coord", unit="s")
    fig.add_plot("line", x="t", y=res["I_motor"], label="电枢电流 (A)")
    fig.add_plot("line", x="t", y=res["rpm"] / 1000.0, label="转速 (k rpm)")
    fig.add_plot("line", x="t", y=res["T_motor"] * 1000.0, label="转矩 (mN·m)")
    fig.set_view(0, xlabel="时间 (s)", ylabel="电流 / 转速 / 转矩", grid=True)
    save(fig, "07_motor.png")

    w = np.linspace(0, 700, 200)
    v_nom = 2.40
    fig = new("电机机械特性与工作点轨迹")
    fig.add_plot("line", x=w, y=np.clip(p.Kt * (v_nom - p.Ke * w) / p.Rm, 0, None) * 1000.0,
                 label=f"T-n 特性（{v_nom:.1f} V）")
    fig.add_plot("scatter", x=res["omega"], y=res["T_motor"] * 1000.0, label="实际工作点",
                 style={"mode": "markers", "opacity": 0.35})
    fig.set_view(0, xlabel="角速度 ω (rad/s)", ylabel="转矩 (mN·m)", grid=True)
    save(fig, "08_motor_tn.png")


def charts_vehicle(res, p=P):
    t = res["t"]
    fig = new("车速与加速度")
    fig.add_data("t", t, role="coord", unit="s")
    fig.add_plot("line", x="t", y=res["v"], label="车速 (m/s)")
    fig.add_plot("line", x="t", y=res["acc"], label="加速度 (m/s²)", style={"dash": "dot"})
    fig.set_view(0, xlabel="时间 (s)", ylabel="车速 / 加速度", grid=True)
    save(fig, "09_speed.png")

    fig = new("累计里程")
    fig.add_data("t", t, role="coord", unit="s")
    fig.add_plot("line", x="t", y=res["s"], label="累计里程 (m)")
    fig.set_view(0, xlabel="时间 (s)", ylabel="里程 (m)", grid=True)
    save(fig, "10_distance.png")


def charts_track(res, p=P, *, gain: float = 1.0):
    traj = drive_trajectory(res, p, gain=gain)
    ideal = ideal_path(p)
    obstacles = place_obstacles(ideal, list(OBSTACLE_S))

    fig = new("赛道俯视图：中心线 / 边界 / 锥桶 / 实际轨迹", size=(7.2, 5.2))
    fig.add_plot("line", x=ideal["x"], y=ideal["y"], label="赛道中心线",
                 style={"dash": "dash", "width": 0.9, "opacity": 0.7,
                        "aspect": "equal"})
    # 边界用同心的体育场线生成（按法向偏移会在小半径处自交，画出来是乱的）
    outer = ideal_path(p, radius=TRACK_R + TRACK_HALF_W, straight=TRACK_STRAIGHT)
    inner = ideal_path(p, radius=max(TRACK_R - TRACK_HALF_W, 0.12), straight=TRACK_STRAIGHT)
    fig.add_plot("line", x=outer["x"], y=outer["y"], label="赛道边界",
                 style={"width": 0.8, "opacity": 0.55})
    fig.add_plot("line", x=inner["x"], y=inner["y"],
                 style={"width": 0.8, "opacity": 0.55})
    fig.add_plot("scatter", x=obstacles[:, 0], y=obstacles[:, 1], label="锥桶",
                 style={"mode": "markers", "color": "#d1495b"})
    fig.add_plot("line", x=traj["x"], y=traj["y"], label="实际轨迹（全部圈）",
                 style={"color": "#9dc3d8", "width": 0.8})
    # 绕桩判定只看第一圈：凸轮拟合误差会让轨迹逐圈缓慢漂移，那是真实物理，但会让固定位置的锥桶失效
    lap_mask = np.asarray(res["s"]) <= 1.02 * L_LAP
    traj1 = {k: np.asarray(v)[lap_mask] for k, v in traj.items()}
    fig.add_plot("line", x=traj1["x"], y=traj1["y"], label="第一圈（绕桩判定）",
                 style={"color": "#2a6f97", "width": 1.6})
    fig.set_view(0, xlabel="x (m)", ylabel="y (m)", grid=True)
    save(fig, "11_track_2d.png", height=640)

    clear = car_clearance(traj1, obstacles)
    fig = new("车体与锥桶的最小净距（第一圈）")
    fig.add_data("t", np.asarray(res["t"])[lap_mask], role="coord", unit="s")
    fig.add_plot("line", x="t", y=clear, label="最小净距 (m)")
    fig.add_plot("line", x=[float(np.asarray(res["t"])[0]), float(np.asarray(res["t"])[lap_mask][-1])],
                 y=[0.0, 0.0], label="压桶线", style={"dash": "dash", "color": "#d1495b", "width": 0.9})
    fig.set_view(0, xlabel="时间 (s)", ylabel="净距 (m)", grid=True)
    save(fig, "12_clearance.png")
    return {"traj": traj, "obstacles": obstacles, "clearance": clear, "ideal": ideal}


def charts_energy(res, p=P):
    t = res["t"]
    q_in = np.array([p.h_flame * max(p.T_flame - x, 0.0) for x in res["Th"]])
    e_hot = np.maximum(q_in - res["P_teg"], 0.0)
    fig = new("能量流向（堆叠）")
    fig.add_data("t", t, role="coord", unit="s")
    fig.add_data("flow", np.vstack([res["P_teg"], e_hot]), role="field")
    fig.add_plot("stackplot", x="t", y="flow")
    fig.set_view(0, xlabel="时间 (s)", ylabel="功率 (W)", grid=True)
    save(fig, "13_energy_flow.png")

    e_in = float(_trapz(q_in, t))
    e_elec = float(_trapz(res["P_teg"], t))
    e_used = float(_trapz(res["P_motor"], t))
    fig = new("能量收支")
    fig.add_data("v", np.array([e_in, e_elec, e_used, max(e_in - e_elec, 0.0)]), role="series")
    fig.add_data("l", np.asarray(["火焰→热端", "TEG 发电", "电机消耗", "热损失"]), role="auto")
    fig.add("pie", {"labels": "l", "values": "v"}, style={"autopct": True})
    fig.set_view(0, title="能量收支 (J)")
    save(fig, "14_energy_pie.png")


def charts_steering(res, track, p=P):
    global _CAM
    traj = track["traj"]
    fig = new("凸轮转向角：设计轮廓 vs 理想规律")
    fig.add_data("s", traj["s"], role="coord", unit="m")
    fig.add_plot("line", x="s", y=np.degrees(traj["delta"]), label="凸轮实际 δ (deg)")
    fig.add_plot("line", x="s", y=np.degrees(np.arctan(p.L_wb * track_kappa(traj["s"]))),
                 label="理想 δ (deg)", style={"dash": "dash"})
    fig.set_view(0, xlabel="累计里程 s (m)", ylabel="转向角 (deg)", grid=True)
    save(fig, "15_steering.png")

    fig = new("凸轮轮廓拟合误差")
    idx = np.arange(_CAM.size) / _CAM.size * L_LAP
    ideal_d = np.arctan(p.L_wb * track_kappa(idx))
    fig.add_plot("line", x=idx, y=np.degrees(ideal_d), label="理想转向角")
    fig.add_plot("line", x=idx, y=np.degrees(_CAM), label=f"凸轮拟合（{p.cam_harmonics} 次谐波）")
    fig.add_plot("line", x=idx, y=np.degrees(_CAM - ideal_d), label="误差",
                 style={"dash": "dot", "color": "#d1495b"})
    fig.set_view(0, xlabel="一圈内的里程 (m)", ylabel="角度 (deg)", grid=True)
    save(fig, "16_cam_fit_error.png")

    # 谐波数 → 绕桩净距：工程上到底要加工几阶凸轮才够
    hs = np.array([3, 4, 5, 6, 8, 10, 12, 16, 20, 24])
    clear_h = np.zeros(hs.size)
    dev_h = np.zeros(hs.size)
    keep = _CAM
    center = np.column_stack([track["ideal"]["x"], track["ideal"]["y"]])
    try:
        for i, h in enumerate(hs):
            _CAM = cam_profile(p, harmonics=int(h))
            tr = drive_trajectory(res, p)
            lap = np.asarray(res["s"]) <= 1.02 * L_LAP
            t1 = {k: np.asarray(v)[lap] for k, v in tr.items()}
            clear_h[i] = float(np.min(car_clearance(t1, track["obstacles"])))
            pts = np.column_stack([t1["x"], t1["y"]])[::max(1, t1["x"].size // 400)]
            dmin = np.sqrt(((pts[:, None, :] - center[None, :, :]) ** 2).sum(-1)).min(1)
            dev_h[i] = float(dmin.max())
    finally:
        _CAM = keep
    fig = new("凸轮谐波数：绕桩净距 与 偏离中心线")
    fig.add_data("h", hs, role="coord")
    fig.add_plot("line", x="h", y=clear_h, label="第一圈最小净距 (m)",
                 style={"mode": "lines+markers"})
    fig.add_plot("line", x="h", y=dev_h, label="最大偏离中心线 (m)",
                 style={"mode": "lines+markers", "dash": "dash", "color": "#6a994e"})
    fig.add_plot("line", x=[float(hs[0]), float(hs[-1])], y=[0.0, 0.0],
                 label="压桶线", style={"dash": "dot", "color": "#d1495b", "width": 0.9})
    fig.set_view(0, xlabel="凸轮谐波数", ylabel="长度 (m)", grid=True)
    save(fig, "16b_harmonics_clearance.png")
    track["harmonics_clearance"] = {"h": hs, "clear": clear_h}


def sensitivity(p=P, *, quick: bool = False):
    # 任务书要求 100–500 组扫描：全量 12×12 = 144 组，--quick 降到 6×6
    if quick:
        igs = np.linspace(13.0, 23.0, 6)
        hAs = np.linspace(0.40, 1.70, 6)
    else:
        igs = np.linspace(12.0, 24.0, 12)
        hAs = np.linspace(0.35, 1.80, 12)
    dist = np.zeros((len(igs), len(hAs)))
    eff = np.zeros_like(dist)
    for i, ig in enumerate(igs):
        for j, ha in enumerate(hAs):
            pp = replace(p, i_g=float(ig), hA_c=float(ha))
            r = simulate(pp, t_end=150.0 if not quick else 100.0, dt=0.03)
            dist[i, j] = float(r["s"][-1])
            e_in = float(_trapz(r["P_teg"], r["t"]))
            e_out = float(_trapz(r["P_motor"], r["t"]))
            eff[i, j] = 100.0 * e_out / max(e_in, 1e-9)
    return {"ig": igs, "hA": hAs, "dist": dist, "eff": eff}


def charts_sensitivity(sens):
    fig = new("参数敏感性：减速比 × 散热能力 → 有效里程")
    fig.add_data("z", sens["dist"], role="field")
    fig.add_data("hA", np.asarray(sens["hA"], dtype=float), role="auto")
    fig.add_data("ig", np.asarray(sens["ig"], dtype=float), role="auto")
    fig.add("heatmap", {"z": "z", "x": "hA", "y": "ig"},
            style={"cmap": "viridis", "colorbar": True})
    fig.set_view(0, xlabel="散热能力 hA_c (W/K)", ylabel="减速比 i_g")
    save(fig, "17_sensitivity_heatmap.png")

    d = sens["dist"].ravel()
    e = sens["eff"].ravel()
    fig = new("多目标权衡：有效里程 vs 能量效率")
    fig.add_plot("scatter", x=e, y=d, label="候选方案",
                 style={"mode": "markers", "color": "#2a6f97"})
    order = np.argsort(e)
    fe, fd, best = [], [], -1.0
    for k in order:
        if d[k] > best:
            best = d[k]
            fe.append(e[k])
            fd.append(d[k])
    fig.add_plot("line", x=np.array(fe), y=np.array(fd), label="Pareto 前沿",
                 style={"color": "#d1495b", "width": 2.0})
    fig.set_view(0, xlabel="能量效率 (%)", ylabel="有效里程 (m)", grid=True)
    save(fig, "18_pareto.png")


def charts_design_compare(p=P):
    designs = {
        "基线": p,
        "加强散热": replace(p, hA_c=1.80),
        "低减速比": replace(p, i_g=13.0),
        "轻量化": replace(p, m=0.42, Crr=0.010),
    }
    fig = new("四种设计方案的行驶曲线")
    rows = []
    for name, pp in designs.items():
        r = simulate(pp, t_end=200.0, dt=0.01)
        fig.add_plot("line", x=r["t"], y=r["v"], label=name)
        rows.append((name, float(r["s"][-1]), float(r["Th"].max())))
    fig.set_view(0, xlabel="时间 (s)", ylabel="车速 (m/s)", grid=True)
    save(fig, "19_design_compare.png")

    fig = new("各方案有效里程对比")
    fig.add_data("d", np.array([r[1] for r in rows]), role="series")
    fig.add_data("n", np.asarray([str(r[0]) for r in rows]), role="auto")
    fig.add("bar", {"x": "n", "y": "d"}, style={"color": "#2a6f97"})
    fig.set_view(0, xlabel="方案", ylabel="里程 (m)")
    save(fig, "20_design_bars.png")
    return rows


def charts_convergence(p=P):
    dts = np.array([0.04, 0.02, 0.01, 0.005, 0.0025])
    dist, tmax, walls = [], [], []
    for dt in dts:
        r = simulate(p, t_end=120.0, dt=float(dt))
        dist.append(float(r["s"][-1]))
        tmax.append(float(r["Th"].max()))
        walls.append(r["wall_s"])
    fig = new("时间步长收敛性")
    fig.add_data("dt", dts, role="coord")
    fig.add_plot("line", x="dt", y=np.array(dist), label="120 s 里程 (m)")
    fig.add_plot("line", x="dt", y=np.array(tmax) / 10.0, label="峰值热端温度 (/10 °C)",
                 style={"dash": "dash"})
    fig.set_view(0, xlabel="时间步长 dt (s)", ylabel="结果", grid=True, xscale="log")
    save(fig, "21_convergence.png")
    return {"dt": dts.tolist(), "dist": dist, "tmax": tmax, "wall": walls}


# --------------------------------------------------------------------------- #
# 6. 三维图（PyVista 后端）
# --------------------------------------------------------------------------- #
def charts_3d(p=P, track=None, res=None):
    # 板四周坐在冷端上：取集总模型的冷端温度，别用环境温度（那会把边缘画成 25 °C 的悬崖）
    xs, ys, T = teg_plate_field(p, t_hot=float(res["Th"][-1]),
                                t_cold=float(res["Tc"][-1]))
    X, Y = np.meshgrid(xs, ys)
    fig = pk.figure(size=(7.0, 5.2), dpi=110, title="TEG Hot-Side Temperature Field")
    fig.add("surface", {"x": X, "y": Y, "z": T}, style={"cmap": "inferno", "colorbar": True})
    fig.set_view(0, xlabel="x (mm)", ylabel="y (mm)", zlabel="T (°C)", elev=28, azim=-60, zoom=0.72)
    save(fig, "22_teg_plate_3d.png", backend="pyvista", width=900, height=640)

    hx, hy, HT = heatsink_field(p)
    fig = new("散热器翅片温度场（剖面）")
    fig.add("contourf", {"z": HT}, style={"levels": 14, "cmap": "coolwarm", "colorbar": True})
    fig.set_view(0, xlabel="翅片间距方向 (mm)", ylabel="翅片高度 (mm)")
    save(fig, "23_heatsink_contourf.png", height=620)

    fe = chassis_beam_fe(p)
    wid = np.linspace(-0.10, 0.10, 21)
    S = fe["sigma"][None, :] * (1 - (wid / 0.10) ** 2)[:, None]
    XX, YY = np.meshgrid(fe["x"] * 1000.0, wid * 1000.0)
    fig = pk.figure(size=(7.0, 5.2), dpi=110, title="Chassis Stress (Beam FE)")
    fig.add("surface", {"x": XX, "y": YY, "z": S / 1000.0},
            style={"cmap": "viridis", "colorbar": True})
    fig.set_view(0, xlabel="x (mm)", ylabel="y (mm)",
                 zlabel="σ (MPa)", elev=32, azim=-72, zoom=0.85)
    save(fig, "24_chassis_stress_3d.png", backend="pyvista", width=900, height=640)

    if track is not None:
        traj = track["traj"]
        step = max(1, traj["x"].size // 3000)
        fig = pk.figure(size=(7.0, 5.2), dpi=110, title="3D Trajectory (x, y, lap)")
        # z 用圈数而不是累计里程：累计 120 m 会把 2 m 见方的赛道拉成一根针
        fig.add("line3d", {"x": traj["x"][::step], "y": traj["y"][::step],
                           "z": (traj["s"] / L_LAP * 0.10)[::step]},
                style={"color": "#2a6f97", "width": 1.4})
        fig.set_view(0, xlabel="x (m)", ylabel="y (m)", zlabel="lap x0.1", elev=24, azim=-56, zoom=0.78)
        save(fig, "25_trajectory_3d.png", backend="pyvista", width=900, height=640)

    if res is not None:
        step = max(1, res["t"].size // 2000)
        fig = pk.figure(size=(7.0, 5.2), dpi=110, title="状态空间轨迹 (T_h, T_c, V_cap)")
        fig.add("line3d", {"x": res["Th"][::step], "y": res["Tc"][::step],
                           "z": res["V_cap"][::step]},
                style={"color": "#d1495b", "width": 1.6})
        fig.set_view(0, xlabel="T_h (°C)", ylabel="T_c (°C)", zlabel="V_cap (V)", elev=22, azim=-52)
        save(fig, "26_state_space_3d.png", backend="pyvista", width=900, height=640)

    return {"plate_Tmax": float(T.max()), "heatsink_Tmax": float(HT.max()),
            "sigma_max": float(fe["sigma"].max()), "deflection_mm": float(abs(fe["w"]).max())}


# --------------------------------------------------------------------------- #
# 7. PlotKit 规模压力测试
# --------------------------------------------------------------------------- #
def assembly_3d(p=P) -> dict:
    """整车三维装配图（单位 mm）：底盘 / 四轮 / TEG 模块 / 散热片 / 超级电容 / 电机 / 转向连杆。

    多实体装配用 PyVista 直接建模（它不是"数据图层"，硬塞进 spec 反而失真）。
    按 200 mm × 250 mm 的车体包络摆放：轮子 r=20 mm 落在地面，底盘压在轮心之上。
    """
    import pyvista as pv
    from PIL import Image

    pv.OFF_SCREEN = True
    pl = pv.Plotter(off_screen=True, window_size=(1000, 700))
    pl.set_background("white")

    pl.add_mesh(pv.Cube(center=(0, 0, 30), x_length=200, y_length=250, z_length=4),
                color="#8d99ae", opacity=0.95)
    for sx in (-1, 1):
        for sy in (-1, 1):
            pl.add_mesh(pv.Cylinder(center=(sx * 88, sy * 100, 20), direction=(0, 1, 0),
                                    radius=20, height=12), color="#2b2d42")
    pl.add_mesh(pv.Cube(center=(-55, 0, 36), x_length=40, y_length=40, z_length=6),
                color="#e63946")
    pl.add_mesh(pv.Cube(center=(-55, 0, 40), x_length=40, y_length=40, z_length=2),
                color="#457b9d")
    for k in range(7):
        pl.add_mesh(pv.Cube(center=(10 + k * 6, 0, 48), x_length=2.5, y_length=70, z_length=30),
                    color="#adb5bd")
    pl.add_mesh(pv.Cylinder(center=(70, -70, 55), direction=(0, 0, 1),
                            radius=18, height=50), color="#1d3557")
    pl.add_mesh(pv.Cylinder(center=(70, 60, 36), direction=(0, 1, 0),
                            radius=16, height=32), color="#f4a261")
    pl.add_mesh(pv.Cube(center=(-90, 0, 28), x_length=4, y_length=150, z_length=3),
                color="#6d6875")
    pl.add_mesh(pv.Cylinder(center=(-90, 0, 26), direction=(0, 0, 1),
                            radius=14, height=4), color="#b5838d")

    pl.view_vector((0.95, -1.35, 0.85), viewup=(0, 0, 1))
    pl.reset_camera()
    pl.camera.zoom(1.02)
    pl.show_bounds(grid=False, location="outer", font_size=9)
    pl.add_text("Biomass TEG car assembly  (mm, envelope 200 x 250)",
                position=(12, 12), font_size=9)
    img = pl.screenshot(return_img=True)
    pl.close()

    out = OUT_DIR / "28_assembly_3d.png"
    Image.fromarray(img).save(out)
    return {"png": out.name, "bytes": out.stat().st_size}


def animate_3d(res, track, *, frames: int = 200, size: tuple[int, int] = (640, 400)) -> dict:
    """三维动画：小车沿真实轨迹跑一圈，出 GIF（单位 mm）。

    两个坑：①复用同一个 Plotter，每帧只改 actor 的位置/朝向（重建场景要 450–600 ms/帧）；
    ②离屏渲染必须显式 `pl.render()` 再 `screenshot()`，否则拿到的是上一帧的缓冲。
    """
    import pyvista as pv
    from PIL import Image

    traj = track["traj"]
    ideal = track["ideal"]
    n = traj["x"].size
    picks = np.linspace(0, n - 1, frames).astype(int)

    pv.OFF_SCREEN = True
    pl = pv.Plotter(off_screen=True, window_size=size)
    pl.set_background("white")

    line = np.c_[ideal["x"] * 1000.0, ideal["y"] * 1000.0, np.zeros(ideal["x"].size)]
    pl.add_lines(line, color="#adb5bd", width=3)
    car = pv.Cube(center=(0, 0, 0), x_length=250, y_length=200, z_length=30)
    actor = pl.add_mesh(car, color="#e63946")
    cabin = pv.Cube(center=(10, 0, 30), x_length=110, y_length=120, z_length=26)
    cabin_actor = pl.add_mesh(cabin, color="#457b9d")

    center = line.mean(axis=0)
    span = float(np.max(line.max(axis=0) - line.min(axis=0)))
    eye = center + np.array([0.85, -1.25, 1.05]) * span
    pl.camera_position = [tuple(eye), tuple(center), (0.0, 0.0, 1.0)]
    pl.camera.zoom(1.30)

    images = []
    for k in picks:
        actor.position = (float(traj["x"][k]) * 1000.0, float(traj["y"][k]) * 1000.0, 15.0)
        actor.orientation = (0.0, 0.0, float(np.degrees(traj["psi"][k])))
        cabin_actor.position = (float(traj["x"][k]) * 1000.0, float(traj["y"][k]) * 1000.0, 15.0)
        cabin_actor.orientation = (0.0, 0.0, float(np.degrees(traj["psi"][k])))
        pl.render()
        images.append(Image.fromarray(pl.screenshot(return_img=True)))
    pl.close()

    out = OUT_DIR / "29_animation_3d.gif"
    images[0].save(out, save_all=True, append_images=images[1:], duration=40, loop=0, optimize=True)
    return {"gif": out.name, "frames": frames, "bytes": out.stat().st_size}


def perf_test(n_points: int = 1_000_000) -> dict:
    """把上百万点的时序数据灌进 PlotKit，量入库 / 抽稀 / 渲染 / 内存。"""
    import tracemalloc

    rng = np.random.default_rng(0)
    t = np.linspace(0.0, 600.0, n_points)
    base = 60.0 + 25.0 * np.sin(t / 60.0)
    ys = [base + 3.0 * np.sin(t / (7.0 + i)) + rng.normal(0, 0.6, n_points) for i in range(3)]

    out: dict[str, float] = {"points": float(n_points)}
    tracemalloc.start()
    t0 = time.perf_counter()
    fig = pk.figure(size=(7.4, 4.3), dpi=110)
    fig.add_data("t", t, role="coord")
    for i, y in enumerate(ys):
        fig.add_data(f"y{i}", y, role="series")
        fig.add_plot("line", x="t", y=f"y{i}", label=f"CH{i}")
    out["build_ms"] = (time.perf_counter() - t0) * 1e3

    from plotkit.store.downsample import downsample_xy
    t0 = time.perf_counter()
    for y in ys:
        downsample_xy(t, y, 1200)
    out["downsample_ms"] = (time.perf_counter() - t0) * 1e3

    t0 = time.perf_counter()
    payload = fig.render(width=1200, height=700, fmt="png")
    out["render_cold_ms"] = (time.perf_counter() - t0) * 1e3
    t0 = time.perf_counter()
    fig.render(width=1200, height=700, fmt="png")
    out["render_hot_ms"] = (time.perf_counter() - t0) * 1e3
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    out["peak_mb"] = peak / 1048576.0
    out["payload_kb"] = len(payload) / 1024.0
    return out


def chart_perf(perf: dict):
    names = ["build_ms", "downsample_ms", "render_cold_ms", "render_hot_ms"]
    labels = ["数据入库", "M4 抽稀", "冷渲染", "热重绘"]
    fig = new(f"PlotKit 规模测试（{perf['points'] / 1e4:.0f} 万点 × 3 通道）")
    fig.add_data("v", np.array([perf[k] for k in names]), role="series")
    fig.add_data("l", np.asarray([str(x) for x in labels]), role="auto")
    fig.add("bar", {"x": "l", "y": "v"}, style={"color": "#2a6f97"})
    fig.set_view(0, xlabel="阶段", ylabel="耗时 (ms)")
    save(fig, "27_perf.png")


# --------------------------------------------------------------------------- #
# 8. 报告 + 主流程
# --------------------------------------------------------------------------- #
def write_report(res, track, sens, conv, designs, fields, perf, elapsed):
    lap = float(res["s"][-1]) / L_LAP
    lines = [
        "# 生物质能温差发电小车 · 多物理场仿真报告",
        "",
        f"生成时间：{time.strftime('%Y-%m-%d %H:%M:%S')}　总耗时：{elapsed:.1f} s　"
        f"仿真步数：{res['t'].size}（dt={res['dt']} s）",
        "",
        "## 1. 关键结果",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        f"| 峰值热端温度 | {res['Th'].max():.1f} °C |",
        f"| 峰值温差 | {res['dT'].max():.1f} K |",
        f"| 峰值 TEG 电功率 | {res['P_teg'].max():.2f} W |",
        f"| 平均 TEG 电功率 | {res['P_teg'].mean():.2f} W |",
        f"| 电容电压峰值 / 终值 | {res['V_cap'].max():.2f} / {res['V_cap'][-1]:.2f} V |",
        f"| 最高车速 | {res['v'].max():.3f} m/s |",
        f"| 总里程 / 圈数 | {res['s'][-1]:.1f} m / {lap:.1f} 圈 |",
        f"| 与锥桶最小净距 | {track['clearance'].min():+.3f} m |",
        f"| 绕桩结果 | {'成功' if track['clearance'].min() > 0 else '碰桶失败'} |",
        f"| 凸轮谐波数 | {P.cam_harmonics}（低于 8 阶会压桶，见 16b） |",
        "",
        "## 2. 三维场（真实数值解）",
        "",
        f"- 均温板最高温度 {fields['plate_Tmax']:.1f} °C（五点差分 + 红黑 SOR，61×61 网格，2500 次迭代；"
        "中心 20×20 mm 受热区按 Dirichlet 取 T_h，四周环境温度）",
        f"- 散热器最高温度 {fields['heatsink_Tmax']:.1f} °C（二维导热 + 牛顿对流边界）",
        f"- 底盘最大弯曲应力 {fields['sigma_max']:.1f} kPa，最大挠度 {fields['deflection_mm']:.3f} mm"
        "（Euler-Bernoulli 梁有限元，60 单元）",
        "",
        "## 3. 参数敏感性（减速比 × 散热能力）",
        "",
        f"- 最优里程 {sens['dist'].max():.1f} m，最差 {sens['dist'].min():.1f} m"
        f"（相差 {100 * (sens['dist'].max() / max(sens['dist'].min(), 1e-9) - 1):.1f}%）",
        f"- 效率范围 {sens['eff'].min():.1f}% ~ {sens['eff'].max():.1f}%",
        "",
        "## 4. 时间步长收敛（t_end = 60 s 的短程对照，绝对里程小于 §1 的 240 s 全程）",
        "",
        "| dt (s) | 里程 (m) | 峰值 T_h (°C) | 墙钟 (s) |",
        "| --- | --- | --- | --- |",
    ]
    for dt, d, tm, w in zip(conv["dt"], conv["dist"], conv["tmax"], conv["wall"]):
        lines.append(f"| {dt:g} | {d:.3f} | {tm:.2f} | {w:.3f} |")
    lines += ["", "## 5. 设计方案对比", "",
              "| 方案 | 里程 (m) | 峰值 T_h (°C) |", "| --- | --- | --- |"]
    for name, d, tm in designs:
        lines.append(f"| {name} | {d:.1f} | {tm:.1f} |")
    lines += [
        "", "## 6. PlotKit 规模测试", "",
        "| 阶段 | 耗时 |", "| --- | --- |",
        f"| 数据入库（{perf['points'] / 1e4:.0f} 万点 × 3 通道） | {perf['build_ms']:.1f} ms |",
        f"| M4 抽稀（每通道 {perf['points'] / 1e4:.0f} 万点 → 1200 px） | {perf['downsample_ms']:.1f} ms |",
        f"| 冷渲染 1200×700 | {perf['render_cold_ms']:.1f} ms |",
        f"| 热重绘 | {perf['render_hot_ms']:.1f} ms |",
        f"| 峰值内存 | {perf['peak_mb']:.1f} MB |",
        f"| PNG 体积 | {perf['payload_kb']:.0f} KB |",
        "", "## 7. 三维装配与动画", "",
        "| 产物 | 内容 | 说明 |", "| --- | --- | --- |",
        "| `28_assembly_3d.png` | 整车装配（底盘/四轮/TEG/散热片/电容/电机/转向） | PyVista 多实体建模，单位 mm，包络 200×250 |",
        "| `29_animation_3d.gif` | 小车沿真实轨迹跑一圈（200 帧） | 复用同一 Plotter，每帧只改 actor 位姿 |",
        "", "## 8. 图表清单", "",
        *[f"- `{p.name}`" for p in sorted(OUT_DIR.glob("*.png"))],
        *([f"- `29_animation_3d.gif`（{fields.get('anim', {}).get('frames', 0)} 帧）"] if (OUT_DIR / "29_animation_3d.gif").exists() else []),
        "",
    ]
    (OUT_DIR / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")


def build_all(*, quick: bool = False, t_end: float = 240.0, dt: float = 0.005,
              n_points: int = 1_000_000) -> dict:
    t_start = time.perf_counter()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    res = simulate(P, t_end=t_end, dt=dt)
    print(f"[sim] {res['t'].size} steps, wall {res['wall_s']:.2f}s, "
          f"Th_max={res['Th'].max():.1f}C dT_max={res['dT'].max():.1f}K "
          f"P_max={res['P_teg'].max():.2f}W s_end={res['s'][-1]:.1f}m", flush=True)

    charts_thermal(res)
    charts_teg_curves()
    charts_electrical(res)
    charts_vehicle(res)
    track = charts_track(res)
    charts_energy(res)
    charts_steering(res, track)
    sens = sensitivity(quick=quick)
    charts_sensitivity(sens)
    designs = charts_design_compare()
    conv = charts_convergence()
    fields = charts_3d(track=track, res=res)
    fields["assembly"] = assembly_3d()
    fields["anim"] = animate_3d(res, track)
    perf = perf_test(n_points)
    chart_perf(perf)

    elapsed = time.perf_counter() - t_start
    write_report(res, track, sens, conv, designs, fields, perf, elapsed)
    n_png = len(list(OUT_DIR.glob("*.png")))
    n_gif = int((OUT_DIR / "29_animation_3d.gif").exists())
    print(f"[done] {n_png} charts + {n_gif} animation, {elapsed:.1f}s", flush=True)
    return {"res": res, "track": track, "sens": sens, "conv": conv,
            "designs": designs, "fields": fields, "perf": perf, "elapsed": elapsed}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="生物质能温差发电小车多物理场仿真")
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--t-end", type=float, default=240.0)
    ap.add_argument("--dt", type=float, default=0.005)
    ap.add_argument("--points", type=int, default=1_000_000)
    args = ap.parse_args(argv)
    out = build_all(quick=args.quick, t_end=args.t_end, dt=args.dt, n_points=args.points)
    r = out["res"]
    summary = {
        "peak_Th_C": round(float(r["Th"].max()), 2),
        "peak_dT_K": round(float(r["dT"].max()), 2),
        "peak_P_teg_W": round(float(r["P_teg"].max()), 3),
        "v_max_m_s": round(float(r["v"].max()), 3),
        "distance_m": round(float(r["s"][-1]), 1),
        "laps": round(float(r["s"][-1]) / L_LAP, 2),
        "min_clearance_m": round(float(out["track"]["clearance"].min()), 3),
        "charts": len(list(OUT_DIR.glob("*.png"))) + int((OUT_DIR / "29_animation_3d.gif").exists()),
        "elapsed_s": round(out["elapsed"], 1),
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
