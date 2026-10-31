# -*- coding: utf-8 -*-
"""阶段 F：性能回归基准（产品路径，非孤立微基准）。

覆盖三档：冷导出（PNG/SVG）、热重绘（blit / autoscale）、数据层（抽稀 / 追加 / 入库），
并记录峰值内存。数据形态固定两种，避免"正弦 vs 噪声差 4.9 倍"的测量陷阱。

用法：
    python tools/bench_regress.py                 # 跑一遍，打印表格
    python tools/bench_regress.py --json out.json # 同时落盘 JSON
    python tools/bench_regress.py --check         # 超预算返回非零（CI 用）

预算（p50，1200x700@100dpi、6 通道 x 20k 点，宽松上限，只防大退化）：
    cold_png <= 400ms, cold_svg <= 700ms, hot_blit <= 120ms, hot_autoscale <= 220ms,
    downsample_2m <= 60ms, append_total <= 200ms
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import plotkit as pk                      # noqa: E402
from plotkit.backends import livecache    # noqa: E402
from plotkit.store import downsample as ds  # noqa: E402

W, H, DPI = 1200, 700, 100
CH, NPTS = 6, 20_000
WARM, REPEAT = 2, 5

BUDGET = {
    "cold_png": 400.0,
    "cold_svg": 700.0,
    "hot_blit": 120.0,
    "hot_autoscale": 220.0,
    "downsample_2m": 60.0,
    "append_total": 200.0,
}


def _data(shape: str, n: int = NPTS, ch: int = CH):
    rng = np.random.default_rng(1234)
    t = np.linspace(0.0, 5.0, n)
    if shape == "sine":
        ys = [np.sin(t * (1 + i * 0.3)) * (1 + i) for i in range(ch)]
    else:
        ys = [rng.normal(0, 1.0, n).cumsum() / 40.0 for i in range(ch)]
    return t, ys


def _figure(t, ys):
    fig = pk.figure(size=(W / DPI, H / DPI), dpi=DPI)
    fig.add_data("t", t, role="coord")
    for i, y in enumerate(ys):
        fig.add_data(f"c{i}", y, role="series")
        fig.add_plot(x="t", y=f"c{i}", label=f"ch{i}")
    return fig


def _time(fn, warm=WARM, repeat=REPEAT):
    for _ in range(warm):
        fn()
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return statistics.median(samples), min(samples)


def _peak_mb(fn):
    tracemalloc.start()
    tracemalloc.reset_peak()
    fn()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / 1e6


def bench_shape(shape: str) -> dict:
    t, ys = _data(shape)
    out = {"shape": shape}
    lim = {"xlim": (0.0, float(NPTS - 1)), "ylim": (-9.0, 9.0)}

    # --- 冷导出 PNG：强制不走缓存（等价每帧新 Figure） ---
    fig = _figure(t, ys)
    livecache._DISABLED = True
    try:
        out["cold_png"] = _time(lambda: fig.render(width=W, height=H, fmt="png", **lim))
        out["cold_svg"] = _time(lambda: fig.render(width=W, height=H, fmt="svg", **lim))
    finally:
        livecache._DISABLED = False
    out["cold_png_bytes"] = len(fig.render(width=W, height=H, fmt="png", **lim))

    # --- 热重绘：固定视窗（blit） ---
    livecache.get_cache().clear()
    fig2 = _figure(t, ys)
    fig2.render(width=W, height=H, fmt="png", **lim)   # 建缓存
    state = {"k": 0}

    def hot_blit():
        state["k"] += 1
        fig2.store.add("c0", np.sin(t / 500.0 + 0.001 * state["k"]), role="series",
                       life="replace", overwrite=True)
        fig2.render(width=W, height=H, fmt="png", **lim)

    out["hot_blit"] = _time(hot_blit)

    # --- 热重绘：自动缩放（整张重画，仍复用构图） ---
    livecache.get_cache().clear()
    fig3 = _figure(t, ys)
    fig3.render(width=W, height=H, fmt="png")

    def hot_auto():
        state["k"] += 1
        fig3.store.add("c0", np.sin(t / 500.0 + 0.001 * state["k"]), role="series",
                       life="replace", overwrite=True)
        fig3.render(width=W, height=H, fmt="png")

    out["hot_autoscale"] = _time(hot_auto)
    livecache.get_cache().clear()

    # --- 数据层：2M 点抽稀 ---
    n2 = 2_000_000
    x2 = np.linspace(0.0, 10.0, n2, dtype=np.float32)
    y2 = np.sin(x2 * 100).astype(np.float32)
    out["downsample_2m"] = _time(lambda: ds.downsample_xy(x2, y2, W), warm=1, repeat=3)
    out["downsample_2m_peak_mb"] = _peak_mb(lambda: ds.downsample_xy(x2, y2, W))

    # --- 数据层：2000 次追加（每次 1000 点） ---
    store = pk.DataStore()
    store.add("y", np.zeros(0), role="series")
    rng = np.random.default_rng(0)
    chunks = [rng.normal(size=1000) for _ in range(2000)]

    def append_all():
        for c in chunks:
            store.push("y", c)

    out["append_total"] = _time(append_all, warm=0, repeat=1)
    out["append_peak_mb"] = _peak_mb(append_all)
    out["append_lines"] = int(store.get("y").values.size)

    # --- 数据层：入库复制成本 ---
    arr = np.zeros(2_000_000, dtype=np.float64)
    st = pk.DataStore()
    out["add_2m"] = _time(lambda: st.add("a", arr, role="series", overwrite=True), warm=1, repeat=3)
    out["add_2m_peak_mb"] = _peak_mb(lambda: st.add("b", arr, role="series", overwrite=True))
    return out


def _fmt(v):
    return f"{v[0]:.1f} / {v[1]:.1f}" if isinstance(v, tuple) else f"{v:.1f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--shapes", default="sine,noise")
    args = ap.parse_args()

    rows = [bench_shape(s.strip()) for s in args.shapes.split(",") if s.strip()]

    keys = [("cold_png", "冷导出 PNG"),
            ("cold_svg", "冷导出 SVG"),
            ("hot_blit", "热重绘 blit（固定视窗）"),
            ("hot_autoscale", "热重绘 整张重画（自动缩放）"),
            ("downsample_2m", "抽稀 2M 点"),
            ("append_total", "追加 2000x1000 点")]

    print(f"\n{'case':30s} " + " ".join(f"{r['shape']:>18s}" for r in rows) + "   p50/min(ms)")
    for key, label in keys:
        cells = [f"{_fmt(r[key]):>18s}" for r in rows]
        print(f"{label:30s} " + " ".join(cells))

    print("\n内存峰值（tracemalloc, MB）")
    for key, label in [("downsample_2m_peak_mb", "抽稀 2M"), ("append_peak_mb", "追加 2000 次"),
                       ("add_2m_peak_mb", "入库 2M float64")]:
        print(f"  {label:16s} " + "  ".join(f"{r[key]:.1f}" for r in rows))

    failed = []
    for r in rows:
        for key, label in keys:
            if key in BUDGET and r[key][0] > BUDGET[key]:
                failed.append(f"{r['shape']}/{label}: {r[key][0]:.1f}ms > {BUDGET[key]:.0f}ms")

    if args.json:
        Path(args.json).write_text(json.dumps({"results": rows, "budget": BUDGET},
                                              ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nJSON → {args.json}")

    if failed:
        print("\n[FAIL] 超出预算：")
        for f in failed:
            print("  " + f)
        return 1
    print("\n[OK] 全部在预算内")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
