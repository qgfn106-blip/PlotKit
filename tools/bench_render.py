# -*- coding: utf-8 -*-
"""mpl 渲染基准：重建 vs 复用 artist vs blit vs 抽稀。

场景贴近 netlab 实时页：1200x700、6 条曲线、每条 20000 点、浅色主题、有网格与图例。
用法：python tools/bench_render.py
"""
from __future__ import annotations

import statistics
import time

import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

W, H, DPI = 1200, 700, 100
WARM = 3
REPEAT = 9


def _data(n=20_000, seed=0):
    rng = np.random.default_rng(seed)
    t = np.linspace(0.0, 5.0, n)
    return t, [
        np.sin(t * (1 + i * 0.3)) * (1 + i) + rng.normal(0, 0.02, n) for i in range(6)
    ]


def _envelope(y, pixels, per_pixel=2):
    """min-max 包络抽稀（与 plotkit.store.downsample 同思路，独立实现避免依赖）。"""
    n = len(y)
    buckets = max(1, int(pixels * per_pixel) // 2)
    if n <= buckets * 2:
        return y
    idx = np.linspace(0, n - 1, buckets + 1).astype(int)
    out = []
    for i in range(buckets):
        a, b = idx[i], idx[i + 1] + 1
        if b <= a:
            continue
        seg = y[a:b]
        out.append(seg.min())
        out.append(seg.max())
    return np.asarray(out)


def build_figure(t, ys, *, simplify=True, n_points=None):
    if simplify:
        import matplotlib as mpl

        mpl.rcParams["path.simplify"] = True
        mpl.rcParams["path.simplify_threshold"] = 1.0
    fig = Figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor="#f7f8fa")
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    lines = []
    for i, y in enumerate(ys):
        yy = y if n_points is None else _envelope(y, W)
        xx = t if n_points is None else t[: len(yy)]
        (ln,) = ax.plot(xx, yy, lw=1.4, label=f"ch{i}")
        lines.append(ln)
    ax.set_facecolor("#ffffff")
    ax.grid(True, color="#dfe3e8", lw=0.6)
    ax.legend(loc="upper right", fontsize=9)
    ax.set_xlim(0, 5)
    ax.set_ylim(-8, 8)
    return fig, canvas, ax, lines


def timed(fn, *a, **kw):
    samples = []
    for i in range(WARM + REPEAT):
        t0 = time.perf_counter()
        fn(*a, **kw)
        dt = (time.perf_counter() - t0) * 1000
        if i >= WARM:
            samples.append(dt)
    return statistics.median(samples), min(samples)


def main():
    t, ys = _data()
    rows = []

    # 1) 每次重建整张图（现在 PlotKit 的做法）
    def rebuild():
        fig, canvas, ax, lines = build_figure(t, ys)
        canvas.draw()
        canvas.get_renderer()._renderer  # 触发真实渲染

    rows.append(("重建 Figure + draw（现状）", *timed(rebuild)))
    rows.append(("重建 + 抽稀到 2 点/列", *timed(lambda: _rebuild_simplified(t, ys))))

    # 2) 复用 artist：只 set_data + set_xlim
    fig, canvas, ax, lines = build_figure(t, ys)
    canvas.draw()
    state = {"k": 0}

    def reuse():
        for ln, y in zip(lines, ys):
            ln.set_ydata(y * (1 + 0.01 * state["k"]))
        ax.set_xlim(0, 5)
        canvas.draw()
        state["k"] = (state["k"] + 1) % 50

    rows.append(("复用 artist + draw", *timed(reuse)))

    # 3) blit：背景只画一次，之后只重绘数据轴
    fig2, canvas2, ax2, lines2 = build_figure(t, ys)
    canvas2.draw()
    bg = canvas2.copy_from_bbox(fig2.bbox)
    state2 = {"k": 0}

    def blit():
        for ln, y in zip(lines2, ys):
            ln.set_ydata(y * (1 + 0.01 * state2["k"]))
        canvas2.restore_region(bg)
        ax2.draw_artist(lines2[0])
        for ln in lines2[1:]:
            ax2.draw_artist(ln)
        canvas2.blit(fig2.bbox)
        state2["k"] = (state2["k"] + 1) % 50

    rows.append(("blit（背景缓存 + 只画曲线）", *timed(blit)))

    # 4) 抽稀后再 blit
    ys_ds = [_envelope(y, W) for y in ys]
    t_ds = t[: len(ys_ds[0])]
    fig3, canvas3, ax3, lines3 = build_figure(t_ds, ys_ds)
    canvas3.draw()
    bg3 = canvas3.copy_from_bbox(fig3.bbox)
    state3 = {"k": 0}

    def blit_ds():
        for ln, y in zip(lines3, ys_ds):
            ln.set_ydata(y * (1 + 0.01 * state3["k"]))
        canvas3.restore_region(bg3)
        for ln in lines3:
            ax3.draw_artist(ln)
        canvas3.blit(fig3.bbox)
        state3["k"] = (state3["k"] + 1) % 50

    rows.append(("blit + 抽稀", *timed(blit_ds)))

    # 5) 导出 PNG 的编码成本
    def enc():
        import io

        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=DPI)

    rows.append(("PNG 编码（savefig）", *timed(enc)))

    n_src = len(t) * len(ys)
    n_ds = len(ys_ds[0]) * len(ys)
    print(
        f"点规模：原始 {n_src:,} 点 → 抽稀后 {n_ds:,} 点（{W}x{H} @ {DPI}dpi，{len(ys)} 通道）"
    )
    print(f"{'case':34s} {'p50(ms)':>9s} {'min(ms)':>9s}")
    for name, p50, best in rows:
        print(f"{name:34s} {p50:9.1f} {best:9.1f}")


def _rebuild_simplified(t, ys):
    ys_ds = [_envelope(y, W) for y in ys]
    fig, canvas, ax, lines = build_figure(t[: len(ys_ds[0])], ys_ds)
    canvas.draw()


if __name__ == "__main__":
    main()
