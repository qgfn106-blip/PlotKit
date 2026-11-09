# -*- coding: utf-8 -*-
"""阶段 F：性能回归基准（产品路径，非孤立微基准）。

覆盖三档：冷导出（PNG/SVG）、热重绘（blit / autoscale）、数据层（抽稀 / 追加 / 入库），
并记录峰值内存。数据形态固定两种，避免"正弦 vs 噪声差 4.9 倍"的测量陷阱。

用法：
    python tools/bench_regress.py                          # 跑一遍，打印表格
    python tools/bench_regress.py --json out.json          # 落盘机器结果（含硬件指纹）
    python tools/bench_regress.py --check                  # 相对回归带闸门（CI 用）
    python tools/bench_regress.py --check --input m.json   # 用已有测量结果核对

裁定 ⑧-3：CI 只用「相对回归带」，不设绝对毫秒硬阈值。BUDGET 仅保留为
历史信息字段以维持 JSON 形状，任何闸门都不再拿它做毫秒比较。
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
import numpy as np

# 无头、可复现：必须在 import plotkit（会拉起 pyplot）之前钉死 Agg。
matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import plotkit as pk  # noqa: E402
from plotkit.backends import livecache  # noqa: E402
from plotkit.store import downsample as ds  # noqa: E402

W, H, DPI = 1200, 700, 100
CH, NPTS = 6, 20_000
WARM, REPEAT = 2, 5
BASELINE = ROOT / "docs" / "bench_baseline.json"

BUDGET = {
    "cold_png": 400.0,
    "cold_svg": 700.0,
    "hot_blit": 120.0,
    "hot_autoscale": 220.0,
    "downsample_2m": 60.0,
    "append_total": 200.0,
}

# 参与相对回归带比较的计时键（值形如 [p50, min]，单位 ms）。
TIMED_KEYS = tuple(BUDGET)
# 同机重复跑的 p50 抖动来自 matplotlib 字体缓存、CPU 频率、预热与并行负载；
# 本机与多个 agent 并行编译时实测抖动可达 ±70%。±100%（2 倍）放过这类噪声，
# 只抓 2 倍以上的真实退化（docstring 里「正弦 vs 噪声」的倍数陷阱正是要防的）。
# 相对比例随机型快慢同步缩放，不会把慢机器误判成回归；绝非绝对毫秒阈值。
RELATIVE_BAND = 1.00
# 硬件指纹不同（如共享 CI runner）时，绝对耗时不可直接比较：仍打印每条
# 超带数字供人工复核，但降为「信息」，不据此判 drift。同指纹时 ×2 才是闸门。
# G4「3 OS × 2 Python 冷启动矩阵」本轮未覆盖，如实标注而非假装跨机数字可比。
FINGERPRINT_KEYS = ("cpu", "python", "matplotlib", "backend", "resolution")


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
    fig2.render(width=W, height=H, fmt="png", **lim)  # 建缓存
    state = {"k": 0}

    def hot_blit():
        state["k"] += 1
        fig2.store.add(
            "c0",
            np.sin(t / 500.0 + 0.001 * state["k"]),
            role="series",
            life="replace",
            overwrite=True,
        )
        fig2.render(width=W, height=H, fmt="png", **lim)

    out["hot_blit"] = _time(hot_blit)

    # --- 热重绘：自动缩放（整张重画，仍复用构图） ---
    livecache.get_cache().clear()
    fig3 = _figure(t, ys)
    fig3.render(width=W, height=H, fmt="png")

    def hot_auto():
        state["k"] += 1
        fig3.store.add(
            "c0",
            np.sin(t / 500.0 + 0.001 * state["k"]),
            role="series",
            life="replace",
            overwrite=True,
        )
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
    out["add_2m"] = _time(
        lambda: st.add("a", arr, role="series", overwrite=True), warm=1, repeat=3
    )
    out["add_2m_peak_mb"] = _peak_mb(
        lambda: st.add("b", arr, role="series", overwrite=True)
    )
    return out


def _fmt(v):
    return f"{v[0]:.1f} / {v[1]:.1f}" if isinstance(v, tuple) else f"{v:.1f}"


def _fingerprint() -> dict[str, str]:
    """采集真实的软硬件指纹；数值一律来自本机/本仓库，绝不编造。"""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        commit = proc.stdout.strip() if proc.returncode == 0 else ""
    except OSError:
        commit = ""
    return {
        "generated_by": "tools/bench_regress.py --json",
        "captured_commit": commit or "unknown",
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cpu": platform.processor() or platform.machine() or "unknown",
        "python": platform.python_version(),
        "matplotlib": matplotlib.__version__,
        "backend": matplotlib.get_backend(),
        "resolution": f"{W}x{H}@{DPI}dpi",
    }


def _payload(rows: list[dict]) -> dict:
    """机器结果，与 docs/bench_baseline.json 同形。"""
    return {**_fingerprint(), "results": rows, "budget": BUDGET}


def _compare(measured: list[dict], baseline: list[dict]) -> list[str]:
    """相对回归带比较：每个形态/计时键的 p50 相对基线偏移超带即记录。"""
    base = {row.get("shape"): row for row in baseline}
    drifts: list[str] = []
    for row in measured:
        label = row.get("shape")
        ref = base.get(label)
        if ref is None:
            drifts.append(f"{label}: 基线缺少该形态")
            continue
        for key in TIMED_KEYS:
            cur, old = row.get(key), ref.get(key)
            if not (
                isinstance(cur, (list, tuple))
                and isinstance(old, (list, tuple))
                and cur
                and old
            ):
                drifts.append(f"{label}/{key}: 缺少 p50 计时")
                continue
            cur_p50, old_p50 = float(cur[0]), float(old[0])
            if old_p50 <= 0:
                drifts.append(f"{label}/{key}: 基线 p50 非正，无法比较")
                continue
            delta = (cur_p50 - old_p50) / old_p50
            if abs(delta) > RELATIVE_BAND:
                drifts.append(
                    f"{label}/{key}: {cur_p50:.1f}ms vs 基线 {old_p50:.1f}ms"
                    f"（{delta:+.0%}，超出 ±{RELATIVE_BAND:.0%}）"
                )
    return drifts


def _run_check(args: argparse.Namespace) -> int:
    """CI 闸门：读基线 + 相对回归带；硬件指纹不同则只打印 info。"""
    baseline_path = Path(args.baseline)
    if not baseline_path.is_file():
        print(
            f"bench_regress: check=error 缺少基线 {baseline_path}；"
            "先运行 python tools/bench_regress.py --json "
            "docs/bench_baseline.json",
            file=sys.stderr,
        )
        return 1
    try:
        baseline_doc = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"bench_regress: check=error 基线不可读：{exc}", file=sys.stderr)
        return 1
    baseline_rows = baseline_doc.get("results")
    if not isinstance(baseline_rows, list) or not baseline_rows:
        print("bench_regress: check=error 基线 results 为空", file=sys.stderr)
        return 1

    if args.input:
        input_path = Path(args.input)
        if not input_path.is_file():
            print(
                f"bench_regress: check=error 缺少测量结果 {input_path}",
                file=sys.stderr,
            )
            return 1
        try:
            measured_doc = json.loads(input_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(
                f"bench_regress: check=error 测量结果不可读：{exc}",
                file=sys.stderr,
            )
            return 1
        measured_rows = measured_doc.get("results")
        fingerprint = {k: measured_doc.get(k) for k in FINGERPRINT_KEYS}
    else:
        shapes = [s.strip() for s in args.shapes.split(",") if s.strip()]
        measured_rows = [bench_shape(s) for s in shapes]
        fingerprint = {k: v for k, v in _fingerprint().items() if k in FINGERPRINT_KEYS}

    if not isinstance(measured_rows, list) or not measured_rows:
        print("bench_regress: check=error 测量结果 results 为空", file=sys.stderr)
        return 1

    ref_fingerprint = {k: baseline_doc.get(k) for k in FINGERPRINT_KEYS}
    same_machine = fingerprint == ref_fingerprint and all(
        value is not None for value in fingerprint.values()
    )
    drifts = _compare(measured_rows, baseline_rows)
    for line in drifts:
        print(f"  [{'drift' if same_machine else 'info'}] {line}")
    if not same_machine:
        print(
            "  硬件指纹不同：跨机比较仅作参考"
            "（G4 3OS×2Python 矩阵未覆盖），不据此判定 drift"
        )
    if drifts and same_machine:
        print("bench_regress: check=drift")
        return 1
    print("bench_regress: check=ok")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="PlotKit 性能回归基准")
    ap.add_argument("--json", default="", help="落盘机器结果 JSON（与基线同形）")
    ap.add_argument("--check", action="store_true", help="相对回归带闸门（CI 用）")
    ap.add_argument("--shapes", default="sine,noise")
    ap.add_argument("--baseline", default=str(BASELINE), help="基线 JSON 路径")
    ap.add_argument(
        "--input", default="", help="已有测量结果 JSON；不跑基准直接复算（测试用）"
    )
    args = ap.parse_args()

    if args.check:
        return _run_check(args)

    rows = [bench_shape(s.strip()) for s in args.shapes.split(",") if s.strip()]

    keys = [
        ("cold_png", "冷导出 PNG"),
        ("cold_svg", "冷导出 SVG"),
        ("hot_blit", "热重绘 blit（固定视窗）"),
        ("hot_autoscale", "热重绘 整张重画（自动缩放）"),
        ("downsample_2m", "抽稀 2M 点"),
        ("append_total", "追加 2000x1000 点"),
    ]

    print(
        f"\n{'case':30s} "
        + " ".join(f"{r['shape']:>18s}" for r in rows)
        + "   p50/min(ms)"
    )
    for key, label in keys:
        cells = [f"{_fmt(r[key]):>18s}" for r in rows]
        print(f"{label:30s} " + " ".join(cells))

    print("\n内存峰值（tracemalloc, MB）")
    for key, label in [
        ("downsample_2m_peak_mb", "抽稀 2M"),
        ("append_peak_mb", "追加 2000 次"),
        ("add_2m_peak_mb", "入库 2M float64"),
    ]:
        print(f"  {label:16s} " + "  ".join(f"{r[key]:.1f}" for r in rows))

    # BUDGET 仅作历史信息保留在 JSON 中；唯一闸门是 --check 的相对回归带，
    # 不再有任何绝对毫秒硬阈值（裁定 ⑧-3）。
    if args.json:
        Path(args.json).write_text(
            json.dumps(_payload(rows), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        print(f"\nJSON → {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
