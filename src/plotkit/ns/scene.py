"""把 NS 涡旋场写成一份普通 PlotKit Figure（D39：三维数据走 spec 图层）。

这里只做"场 → 图层"的翻译，一行 WebGL 都没有：`volume` 交给浏览器（服务端可抽等值面），
`particles` 交给浏览器的柔光点精灵。于是主查看器、桌面壳、导出脚本看到的是同一份 spec。
"""

from __future__ import annotations

from typing import Any

import numpy as np

from .field import PhysicalParams, SimilarityField, SimilarityParams

__all__ = ["sample_speed", "seed_points", "figure"]


def _cyl(x: np.ndarray, y: np.ndarray, z: np.ndarray):
    """笛卡尔采样点 → 柱坐标所需的 (r, theta, z)，r 与 z 原样保留。"""
    r = np.hypot(x, y)
    return r, np.arctan2(y, x), z


def sample_speed(field: Any, t: float, *, n: int = 48, extent: float = 0.5,
                 z_extent: float = 1.2) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """在规则网格上采速度模长（供 volume 图层用的标量场）。

    返回 `(xs, ys, zs, speed)`，其中 speed 的形状是 `(nz, ny, nx)`（x 变化最快）——
    这正是 `/api/volume` 约定的布局，也是 `fig.add("volume", {...})` 期望的方向。
    """
    n = max(8, int(n))
    xs = np.linspace(-extent, extent, n)
    ys = np.linspace(-extent, extent, n)
    zs = np.linspace(-z_extent, z_extent, n)
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")     # (nx, ny, nz)
    pts = np.stack([X.ravel(), Y.ravel(), Z.ravel()], axis=1)
    vel = np.asarray(field.velocity(pts, t), dtype=np.float64).reshape(-1, 3)
    speed = np.linalg.norm(vel, axis=1).reshape(n, n, n)
    return xs, ys, zs, np.transpose(speed, (2, 1, 0)).copy()   # → (nz, ny, nx)


def seed_points(field: Any, t: float, *, count: int = 12000, extent: float = 0.5,
                z_extent: float = 1.2, shells: int = 26, seed: int = 7
                ) -> tuple[np.ndarray, np.ndarray]:
    """离散同心壳上的示踪种子（确定性），返回 `(xyz, speed)`。

    这个场向轴收缩，纯随机撒点会立刻糊成一团；按壳撒点才能看出"内旋 + 轴向拉伸"。
    """
    rng = np.random.default_rng(seed)
    count = max(64, int(count))
    shells = max(4, int(shells))
    # 85% 撒赤道盘，15% 撒轴向柱（参考视频里的"环盘 + 上锥下锥"）
    n_disk = int(count * 0.85)
    n_col = count - n_disk

    idx = rng.integers(0, shells, n_disk)
    rad = extent * (idx + 0.5) / shells * (0.985 + 0.03 * rng.random(n_disk))
    th = rng.random(n_disk) * 2 * np.pi
    zz = (rng.random(n_disk) * 2 - 1) * 0.035 * z_extent
    disk = np.stack([rad * np.cos(th), rad * np.sin(th), zz], axis=1)

    rad2 = 0.02 + 0.12 * extent * np.sqrt(rng.random(n_col))
    th2 = rng.random(n_col) * 2 * np.pi
    z2 = (rng.random(n_col) * 2 - 1) * z_extent
    taper = 1.0 - 0.78 * np.power(np.abs(z2) / z_extent, 1.1)
    col = np.stack([rad2 * taper * np.cos(th2), rad2 * taper * np.sin(th2), z2], axis=1)

    xyz = np.concatenate([disk, col], axis=0)
    vel = np.asarray(field.velocity(xyz, t), dtype=np.float64)
    return xyz, np.linalg.norm(vel, axis=1)


def figure(field: Any = None, *, t: float = 0.05, n: int = 48, particles: int = 12000,
           extent: float = 0.5, z_extent: float = 1.2, level: float | None = None,
           physical: PhysicalParams | None = None,
           similarity: SimilarityParams | None = None, title: str | None = None):
    """把 NS 场做成一份可直接喂给主查看器的 Figure。

    ```python
    import plotkit as pk
    fig = pk.ns.scene.figure(t=0.05, n=48)
    fig.render(width=900, height=700, backend="pyvista")   # 服务端出图
    ```
    """
    import plotkit as pk

    if field is None:
        if physical is not None:
            field = SimilarityField(physical.to_similarity())
        else:
            field = SimilarityField(similarity or SimilarityParams())

    xs, ys, zs, speed = sample_speed(field, t, n=n, extent=extent, z_extent=z_extent)
    xyz, spd = seed_points(field, t, count=particles, extent=extent, z_extent=z_extent)

    fig = pk.figure(size=(7.2, 5.6), dpi=110, title=title or f"NS vortex · t={t:.3f}")
    fig.add_data("vx", xs, role="coord")
    fig.add_data("vy", ys, role="coord")
    fig.add_data("vz", zs, role="coord")
    fig.add_data("speed", speed, role="field")
    fig.add("volume", {"x": "vx", "y": "vy", "z": "vz", "values": "speed"},
            style={"level": float(level)} if level is not None else {})

    fig.add_data("px", xyz[:, 0], role="auto")
    fig.add_data("py", xyz[:, 1], role="auto")
    fig.add_data("pz", xyz[:, 2], role="auto")
    fig.add_data("pc", spd, role="auto")
    fig.add("particles", {"x": "px", "y": "py", "z": "pz", "scalar": "pc"},
            style={"markersize": 3.0, "opacity": 0.08})
    return fig
