"""NS 涡旋可视化：HTTP 接口（模式 A-prime：前导阶自相似解）。

只做「算 + 传」：场由 plotkit.ns 计算，前端用 WebGL2 渲染。
二进制帧统一为 magic(4) + meta_len(4) + meta(json) + float32 payload。
"""

from __future__ import annotations

import io
import json
import struct
from functools import lru_cache

import numpy as np
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import Response

from ..ns import SimilarityParams, analyze, convergence, profile_table, velocity_at

__all__ = ["router", "MODE_LABEL"]

MODE_LABEL = "Mode A-prime - Leading-order similarity field (not a verified blow-up solution)"

MAGIC = b"PKNS"

FORMULAS = [
    r"$|u(\cdot,t)|_{L^\infty} \sim \tau^{-(1/2+h)}$",
    r"$|\omega(\cdot,t)|_{L^\infty} \sim \tau^{-1}$",
    r"$\tau = 1 - t,\quad r = \sqrt{2qX},\quad z = q^{1/2-h}\,\eta$",
    r"$q = \tau/(1-\eta^2),\quad u_\theta = q^{-(1/2+h)}E(X,\eta)$",
]


def _frame(meta: dict, payload: np.ndarray) -> Response:
    """二进制帧：magic + meta_len + meta + float32 数据。

    meta 补空格到 4 字节对齐——否则前端 `new Float32Array(buffer, offset)` 会抛
    `RangeError: start offset should be a multiple of 4`。
    """
    raw = json.dumps(meta).encode()
    pad = (-len(raw)) % 4
    if pad:
        raw = raw + b" " * pad
    blob = payload.astype(np.float32, copy=False).tobytes()
    head = MAGIC + struct.pack("<I", len(raw))
    return Response(content=head + raw + blob, media_type="application/octet-stream")


@lru_cache(maxsize=8)
def _table(h: float, x0: float, eta0: float):
    p = SimilarityParams(h=h, x0=x0, eta0=eta0)
    return p, profile_table(p)


router = APIRouter(prefix="/api/ns", tags=["ns"])


@router.get("/meta")
def meta() -> dict:
    p, _ = _table(SimilarityParams().h, SimilarityParams().x0, SimilarityParams().eta0)
    return {
        "mode": "A-prime",
        "label": MODE_LABEL,
        "formulas": FORMULAS,
        "params": {"h": p.h, "x0": p.x0, "eta0": p.eta0,
                   "nu": p.nu, "t_blow": p.t_blow},
        "paper_compliant": p.paper_compliant,
        "note": "前导阶自相似解；剖面形状为自选核，h<0.01 才落在论文证明区间。",
    }


@router.get("/slice")
def slice_(t: float = Query(0.5, ge=0.0), n_r: int = Query(192, ge=32, le=512),
           n_z: int = Query(256, ge=32, le=512),
           h: float = Query(0.005), x0: float = Query(0.6), eta0: float = Query(1.0),
           r_max: float = Query(0.35, gt=0.0), z_max: float = Query(1.2, gt=0.0)):
    """轴对称场在 (r,z) 上的一个切片（体积渲染用 2D 纹理，方位角对称）。"""
    if t >= 1.0:
        raise HTTPException(400, "t 必须小于 t_blow=1")
    p, table = _table(h, x0, eta0)
    r = np.linspace(0.0, r_max, n_r)
    z = np.linspace(-z_max, z_max, n_z)
    R, Z = np.meshgrid(r, z, indexing="ij")
    ur, ut, uz = velocity_at(np.maximum(R, 1e-6), Z, t, p, table)

    # 着色标量：角速度 Ω = u_θ/r（涡核里最大，远处衰减），取 log10 便于压动态范围
    omega = np.abs(ut) / np.maximum(R, 1e-6)
    omega = omega.T                                   # (n_z, n_r)，行=z、列=r
    vmax = float(np.percentile(omega[omega > 0], 99.5)) if np.any(omega > 0) else 1.0
    scalar = np.log10(np.maximum(omega, vmax * 1e-4)).astype(np.float32)

    speed = np.sqrt(ur ** 2 + ut ** 2 + uz ** 2).T.astype(np.float32)
    meta = {
        "t": float(t), "tau": float(p.t_blow - t),
        "n_r": n_r, "n_z": n_z, "r_max": float(r_max), "z_max": float(z_max),
        "vmin": float(np.log10(vmax * 1e-4)), "vmax": float(np.log10(vmax)),
        "omega_p995": vmax, "u_max": float(np.sqrt((ur ** 2 + ut ** 2 + uz ** 2).max())),
        "layout": "rows=z, cols=r; scalar then speed",
    }
    payload = np.concatenate([scalar.ravel(), speed.ravel()])
    return _frame(meta, payload)


@router.get("/diagnostics")
def diagnostics(t: float = Query(0.5, ge=0.0),
                h: float = Query(0.005), x0: float = Query(0.6), eta0: float = Query(1.0),
                grid: bool = Query(True), n: int = Query(48, ge=16, le=96)) -> dict:
    if t >= 1.0:
        raise HTTPException(400, "t 必须小于 t_blow=1")
    p, table = _table(h, x0, eta0)
    analytic = analyze(p, t, table=table, n_r=200, n_z=200).as_dict()
    out: dict = {"analytic": analytic, "mode": "A-prime", "label": MODE_LABEL}
    if grid:
        from ..ns import grid_stats

        out["grid"] = grid_stats(p, t, table=table, n=n).as_dict()
    return out


@router.get("/convergence")
def convergence_(t: float = Query(0.5, ge=0.0),
                 h: float = Query(0.005), x0: float = Query(0.6), eta0: float = Query(1.0)) -> dict:
    p, _ = _table(h, x0, eta0)
    return {"t": float(t), "rows": convergence(p, t, sizes=(32, 64, 96))}


@router.get("/formula.svg")
def formula_svg(width: float = Query(7.2, ge=2.0, le=16.0)) -> Response:
    """公式层：matplotlib mathtext 排成 SVG（真矢量，可缩放、可打印）。"""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(width, 0.34 * len(FORMULAS)), dpi=200)
    fig.patch.set_alpha(0.0)
    for i, tex in enumerate(FORMULAS):
        fig.text(0.01, 1.0 - (i + 0.5) / len(FORMULAS), tex,
                 color="#e8edf5", fontsize=11, va="center", ha="left")
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", pad_inches=0.02,
                transparent=True, metadata={"Date": None})
    plt.close(fig)
    return Response(content=buf.getvalue(), media_type="image/svg+xml")


@router.get("/velocity")
def velocity_grid(t: float = Query(0.5, ge=0.0), n: int = Query(48, ge=16, le=96),
                  extent: float = Query(0.35, gt=0.0), z_extent: float = Query(1.0, gt=0.0),
                  h: float = Query(0.005), x0: float = Query(0.6), eta0: float = Query(1.0)):
    """笛卡尔速度网格（供 GPU 三线性插值推进粒子）。n³×(u,v,w) float32。"""
    if t >= 1.0:
        raise HTTPException(400, "t 必须小于 t_blow=1")
    p, table = _table(h, x0, eta0)
    xs = np.linspace(-extent, extent, n).astype(np.float32)
    zs = np.linspace(-z_extent, z_extent, n).astype(np.float32)
    X, Y, Z = np.meshgrid(xs, xs, zs, indexing="ij")
    R = np.hypot(X, Y)
    th = np.arctan2(Y, X)
    ur, ut, uz = velocity_at(np.maximum(R, 1e-6), Z, t, p, table)
    U = (ur * np.cos(th) - ut * np.sin(th)).astype(np.float32)
    V = (ur * np.sin(th) + ut * np.cos(th)).astype(np.float32)
    W = uz.astype(np.float32)
    meta = {"t": float(t), "n": n, "extent": float(extent), "z_extent": float(z_extent),
            "order": "x fastest, then y, then z; interleaved channels u,v,w"}
    # The WebGL sampler indexes one interleaved (u, v, w) triple per
    # point, with x as the fastest spatial axis.
    payload = np.stack([
        U.ravel(order="F"), V.ravel(order="F"), W.ravel(order="F")
    ], axis=1).ravel()
    return _frame(meta, payload)


@router.post("/export")
def export_animation(payload: dict = Body(...)):
    """把前端逐帧抓下来的 canvas 合成 GIF/MP4（保持屏幕上的渲染观感）。

    payload: {"frames": [dataURL...], "fps": 12, "fmt": "gif"|"mp4", "width": 900}
    """
    import base64
    import io
    import shutil
    import subprocess
    import tempfile

    from PIL import Image

    frames = payload.get("frames") or []
    if not frames:
        raise HTTPException(400, "frames 为空")
    fps = int(payload.get("fps") or 12)
    fmt = (payload.get("fmt") or "gif").lower()
    width = int(payload.get("width") or 900)

    images = []
    for data in frames:
        raw = data.split(",", 1)[-1]
        img = Image.open(io.BytesIO(base64.b64decode(raw))).convert("RGB")
        if img.width > width:
            img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
        images.append(img)
    if not images:
        raise HTTPException(400, "帧解码失败")

    if fmt == "gif":
        buf = io.BytesIO()
        images[0].save(buf, format="GIF", save_all=True, append_images=images[1:],
                       duration=max(20, int(1000 / fps)), loop=0, optimize=True)
        return Response(content=buf.getvalue(), media_type="image/gif")
    if fmt == "mp4":
        if not shutil.which("ffmpeg"):
            raise HTTPException(400, "未安装 ffmpeg，无法导出 MP4（可用 GIF）")
        with tempfile.TemporaryDirectory() as tmp:
            for i, img in enumerate(images):
                img.save(f"{tmp}/f{i:04d}.png")
            target = f"{tmp}/out.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(fps),
                            "-i", f"{tmp}/f%04d.png", "-pix_fmt", "yuv420p", target], check=True)
            return Response(content=open(target, "rb").read(), media_type="video/mp4")
    raise HTTPException(400, f"不支持的格式 {fmt}")


@router.get("/arrows")
def arrows(t: float = Query(0.5, ge=0.0), n_r: int = Query(6, ge=2, le=12),
           n_theta: int = Query(20, ge=6, le=48), n_z: int = Query(7, ge=3, le=16),
           r_max: float = Query(0.42, gt=0.0), z_max: float = Query(0.95, gt=0.0),
           h: float = Query(0.005), x0: float = Query(0.6), eta0: float = Query(1.0)):
    """柱坐标稀疏网格上的矢量箭头（任务书图层③）：位置 + 速度，供前端 glyph 批量绘制。"""
    if t >= 1.0:
        raise HTTPException(400, "t 必须小于 t_blow=1")
    p, table = _table(h, x0, eta0)
    rs = np.linspace(r_max / n_r, r_max, n_r, dtype=np.float32)
    thetas = np.linspace(0.0, 2 * np.pi, n_theta, endpoint=False, dtype=np.float32)
    zs = np.linspace(-z_max, z_max, n_z, dtype=np.float32)
    R, TH, Z = np.meshgrid(rs, thetas, zs, indexing="ij")
    ur, ut, uz = velocity_at(np.maximum(R, 1e-6), Z, t, p, table)
    px = (R * np.cos(TH)).ravel().astype(np.float32)
    py = (R * np.sin(TH)).ravel().astype(np.float32)
    pz = Z.ravel().astype(np.float32)
    vx = (ur * np.cos(TH) - ut * np.sin(TH)).ravel().astype(np.float32)
    vy = (ur * np.sin(TH) + ut * np.cos(TH)).ravel().astype(np.float32)
    vz = uz.ravel().astype(np.float32)
    speed = np.sqrt(vx ** 2 + vy ** 2 + vz ** 2)
    meta = {"t": float(t), "count": int(px.size), "n_r": n_r, "n_theta": n_theta, "n_z": n_z,
            "r_max": float(r_max), "z_max": float(z_max),
            "u_max": float(speed.max()) if speed.size else 0.0,
            "u_theta_max": float(np.abs(ut).max()) if ut.size else 0.0,
            "order": "positions xyz then vectors xyz"}
    return _frame(meta, np.concatenate([px, py, pz, vx, vy, vz]))


@router.get("/pathlines")
def pathlines(t0: float = Query(0.0, ge=0.0), t1: float = Query(0.5, gt=0.0),
              seeds: int = Query(180, ge=8, le=800), steps: int = Query(160, ge=16, le=600),
              r_seed: float = Query(0.06, gt=0.0), z_seed: float = Query(0.55, gt=0.0),
              h: float = Query(0.005), x0: float = Query(0.6), eta0: float = Query(1.0)):
    """从环带上释放的种子点做 RK4 积分（真实速度场），返回折线束 + 每帧长度。"""
    if t1 >= 1.0:
        raise HTTPException(400, "t 必须小于 t_blow=1")
    p, table = _table(h, x0, eta0)
    rng = np.random.default_rng(7)
    n = seeds
    theta = rng.uniform(0, 2 * np.pi, n)
    rr = r_seed * np.sqrt(rng.uniform(0.25, 1.0, n))
    zz = rng.uniform(-z_seed, z_seed, n)
    pos = np.stack([rr * np.cos(theta), rr * np.sin(theta), zz], axis=1)

    dt = (t1 - t0) / max(steps - 1, 1)
    out = np.empty((steps, n, 3), dtype=np.float32)
    out[0] = pos

    def vel(pts, tt):
        r = np.hypot(pts[:, 0], pts[:, 1])
        th = np.arctan2(pts[:, 1], pts[:, 0])
        ur, ut, uz = velocity_at(np.maximum(r, 1e-6), pts[:, 2], tt, p, table)
        return np.stack([ur * np.cos(th) - ut * np.sin(th),
                         ur * np.sin(th) + ut * np.cos(th), uz], axis=1)

    cur = pos.copy()
    for i in range(1, steps):
        tt = t0 + dt * (i - 1)
        k1 = vel(cur, tt)
        k2 = vel(cur + 0.5 * dt * k1, tt + 0.5 * dt)
        k3 = vel(cur + 0.5 * dt * k2, tt + 0.5 * dt)
        k4 = vel(cur + dt * k3, tt + dt)
        cur = cur + (dt / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
        out[i] = cur

    meta = {"t0": float(t0), "t1": float(t1), "seeds": n, "steps": steps,
            "layout": "steps x seeds x xyz (float32, x fastest)"}
    return _frame(meta, out.ravel())
