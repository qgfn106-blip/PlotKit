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

WP-4：指纹扩展为硬件 / OS / Python / NumPy / SciPy / BLAS-MKL / 线程 / 输入契约 /
runner 版本；输出四态 PASS / DRIFT / INCOMPARABLE / ERROR；统计口径固定为
p50 / p95 / min / max / 样本数与 RSS + tracemalloc 峰值。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
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
CONFIG_PATH = ROOT / "docs" / "bench_config.json"
RUNNER_VERSION = "plotkit-bench/2"

BUDGET = {
    "cold_png": 400.0,
    "cold_svg": 700.0,
    "hot_blit": 120.0,
    "hot_autoscale": 220.0,
    "downsample_2m": 60.0,
    "append_total": 200.0,
}

# 参与相对回归带比较的计时键（新格式为统计 dict；旧格式 [p50, min] 仍可读）。
TIMED_KEYS = tuple(BUDGET)
# 同机重复跑的 p50 抖动来自 matplotlib 字体缓存、CPU 频率、预热与并行负载；
# 本机与多个 agent 并行编译时实测抖动可达 ±70%。±100%（2 倍）放过这类噪声，
# 只抓 2 倍以上的真实退化（docstring 里「正弦 vs 噪声」的倍数陷阱正是要防的）。
# 相对比例随机型快慢同步缩放，不会把慢机器误判成回归；绝非绝对毫秒阈值。
DEFAULT_RELATIVE_BAND = 1.00
DEFAULT_MEMORY_BAND = 0.50
DEFAULT_SIZE_BAND = 0.50

#: 只有这些字段相同，性能数字才允许比较；captured_at / commit / generated_by
#: 属于「哪次采集」而非「哪台机器 + 哪套输入」，不参与可比性判定。
FINGERPRINT_KEYS = (
    "runner_version",
    "cpu",
    "machine",
    "cpu_count",
    "os",
    "os_release",
    "python",
    "python_implementation",
    "numpy",
    "scipy",
    "matplotlib",
    "backend",
    "resolution",
    "blas",
    "mkl",
    "threads",
    "input_contract_sha256",
)

#: 固定输入契约：任何一项变化都必须让基线变为 INCOMPARABLE，而不是悄悄 PASS。
INPUT_CONTRACT = {
    "figure": {"width": W, "height": H, "dpi": DPI},
    "channels": CH,
    "points": NPTS,
    "seed": 1234,
    "warmup": {"default": WARM, "downsample_2m": 1, "append_total": 0, "add_2m": 1},
    "repeat": {"default": REPEAT, "downsample_2m": 3, "append_total": 1, "add_2m": 3},
    "timing": "time.perf_counter() 包住单次操作；先 warmup 再 repeat；样本统计 p50/p95/min/max",
    "memory": "tracemalloc.reset_peak() 包住单次调用；可选 psutil RSS 前后采样",
}

MEMORY_KEYS = (
    "downsample_2m_peak_mb",
    "append_peak_mb",
    "add_2m_peak_mb",
)
SIZE_KEYS = ("cold_png_bytes",)
# CI 共享 runner 只允许跳过“机器本身”的差异；runner 版本或输入契约变化仍必须
# 判为不可比较，避免把测量工具/输入变化当成硬件差异悄悄放行。
SMOKE_TOLERATED_FINGERPRINT_KEYS = frozenset(FINGERPRINT_KEYS) - {
    "runner_version",
    "input_contract_sha256",
}


def _load_config() -> dict:
    """退化方向与阈值统一由 docs/bench_config.json 提供，缺省值仅作兜底。"""
    config = {
        "relative_band": DEFAULT_RELATIVE_BAND,
        "memory_band": DEFAULT_MEMORY_BAND,
        "size_band": DEFAULT_SIZE_BAND,
        "exit_codes": {"PASS": 0, "DRIFT": 1, "INCOMPARABLE": 2, "ERROR": 3},
    }
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return config
    if isinstance(raw, dict):
        for key in ("relative_band", "memory_band", "size_band"):
            value = raw.get(key)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                config[key] = float(value)
        codes = raw.get("exit_codes")
        if isinstance(codes, dict):
            for status in ("PASS", "DRIFT", "INCOMPARABLE", "ERROR"):
                value = codes.get(status)
                if isinstance(value, int) and value >= 0:
                    config["exit_codes"][status] = value
    return config


CONFIG = _load_config()


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


def _percentile(samples: list[float], fraction: float) -> float:
    if not samples:
        return float("nan")
    ordered = sorted(float(v) for v in samples)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    low = int(math.floor(position))
    high = int(math.ceil(position))
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def _summary(samples: list[float], unit: str = "ms") -> dict:
    clean = [float(v) for v in samples if math.isfinite(float(v))]
    if not clean:
        return {
            "unit": unit,
            "n": 0,
            "samples": [],
            "p50": None,
            "p95": None,
            "min": None,
            "max": None,
            "mean": None,
            "stdev": None,
        }
    return {
        "unit": unit,
        "n": len(clean),
        "samples": [round(v, 6) for v in clean],
        "p50": round(statistics.median(clean), 6),
        "p95": round(_percentile(clean, 0.95), 6),
        "min": round(min(clean), 6),
        "max": round(max(clean), 6),
        "mean": round(statistics.fmean(clean), 6),
        "stdev": round(statistics.pstdev(clean), 6) if len(clean) > 1 else 0.0,
    }


def _time(fn, warm: int = WARM, repeat: int = REPEAT) -> dict:
    for _ in range(max(0, int(warm))):
        fn()
    samples = []
    for _ in range(max(1, int(repeat))):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return _summary(samples)


def _rss_mb():
    try:
        import psutil  # type: ignore

        return round(psutil.Process(os.getpid()).memory_info().rss / 1e6, 3)
    except Exception:
        return None


def _peak_memory(fn) -> dict:
    """单次调用的 tracemalloc 峰值 + 可选的进程 RSS 前后采样。"""
    rss_before = _rss_mb()
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        fn()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    rss_after = _rss_mb()
    return {
        "tracemalloc_peak_mb": round(peak / 1e6, 3),
        "rss_before_mb": rss_before,
        "rss_after_mb": rss_after,
        "rss_delta_mb": (
            round(rss_after - rss_before, 3)
            if rss_before is not None and rss_after is not None
            else None
        ),
        "peak_rss_mb": (
            round(max(rss_before, rss_after), 3)
            if rss_before is not None and rss_after is not None
            else None
        ),
    }


def _blas_name() -> str:
    try:
        config = np.__config__.CONFIG  # type: ignore[attr-defined]
        dependencies = config.get("Build Dependencies", {}) if isinstance(config, dict) else {}
        blas = dependencies.get("blas", {}) if isinstance(dependencies, dict) else {}
        return str(blas.get("name", "unknown")) if isinstance(blas, dict) else "unknown"
    except Exception:
        return "unknown"


def _mkl_version() -> str:
    try:
        import mkl  # type: ignore

        return str(getattr(mkl, "get_version_string", lambda: "unknown")())
    except Exception:
        return "absent"


def _package_version(name: str) -> str:
    try:
        module = __import__(name)
        return str(getattr(module, "__version__", "unknown"))
    except Exception:
        return "absent"


def _threads() -> dict:
    keys = ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")
    return {key: os.environ.get(key, "default") for key in keys}


def _input_contract_hash() -> str:
    payload = json.dumps(INPUT_CONTRACT, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _git_commit() -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else "unknown"
    except OSError:
        return "unknown"


def _fingerprint() -> dict:
    """采集真实的软硬件指纹；数值一律来自本机/本仓库，绝不编造。"""
    return {
        "generated_by": "tools/bench_regress.py --json",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "captured_commit": _git_commit(),
        "runner_version": RUNNER_VERSION,
        "cpu": platform.processor() or platform.machine() or "unknown",
        "machine": platform.machine() or "unknown",
        "cpu_count": os.cpu_count() or 0,
        "os": platform.system() or "unknown",
        "os_release": platform.release() or "unknown",
        "python": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "numpy": _package_version("numpy"),
        "scipy": _package_version("scipy"),
        "matplotlib": _package_version("matplotlib"),
        "backend": str(matplotlib.get_backend()),
        "resolution": f"{W}x{H}@{DPI}dpi",
        "blas": _blas_name(),
        "mkl": _mkl_version(),
        "threads": _threads(),
        "input_contract_sha256": _input_contract_hash(),
    }


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
    memory = _peak_memory(lambda: ds.downsample_xy(x2, y2, W))
    out["downsample_2m_memory"] = memory
    out["downsample_2m_peak_mb"] = memory["tracemalloc_peak_mb"]

    # --- 数据层：2000 次追加（每次 1000 点） ---
    store = pk.DataStore()
    store.add("y", np.zeros(0), role="series")
    rng = np.random.default_rng(0)
    chunks = [rng.normal(size=1000) for _ in range(2000)]

    def append_all():
        for c in chunks:
            store.push("y", c)

    out["append_total"] = _time(append_all, warm=0, repeat=1)
    memory = _peak_memory(append_all)
    out["append_memory"] = memory
    out["append_peak_mb"] = memory["tracemalloc_peak_mb"]
    out["append_lines"] = int(store.get("y").values.size)

    # --- 数据层：入库复制成本 ---
    arr = np.zeros(2_000_000, dtype=np.float64)
    st = pk.DataStore()
    out["add_2m"] = _time(
        lambda: st.add("a", arr, role="series", overwrite=True), warm=1, repeat=3
    )
    memory = _peak_memory(lambda: st.add("b", arr, role="series", overwrite=True))
    out["add_2m_memory"] = memory
    out["add_2m_peak_mb"] = memory["tracemalloc_peak_mb"]
    return out


def _fmt(metric) -> str:
    if isinstance(metric, dict):
        p50, p95 = metric.get("p50"), metric.get("p95")
        if p50 is None:
            return "n/a"
        return f"{p50:.1f} / {p95:.1f}"
    if isinstance(metric, (list, tuple)) and metric:
        return f"{float(metric[0]):.1f} / {float(metric[1]):.1f}"
    if isinstance(metric, (int, float)):
        return f"{float(metric):.1f}"
    return str(metric)


def _payload(rows: list[dict]) -> dict:
    """机器结果，与 docs/bench_baseline.json 同形。"""
    return {
        "schema": "plotkit-bench/2",
        **_fingerprint(),
        "input_contract": INPUT_CONTRACT,
        "results": rows,
        "budget": BUDGET,
    }


def _metric_value(metric):
    """兼容新统计 dict 与旧 [p50, min] 列表，返回 (p50, p95, n)。"""
    if isinstance(metric, dict):
        p50 = metric.get("p50")
        p95 = metric.get("p95", p50)
        n = metric.get("n", len(metric.get("samples", [])))
        return p50, p95, n
    if isinstance(metric, (list, tuple)) and metric:
        return metric[0], metric[1] if len(metric) > 1 else metric[0], 1
    return None, None, 0


def _compare(measured: list[dict], baseline: list[dict], *, config: dict | None = None) -> list[str]:
    """方向性回归：仅当指标变差且超出配置阈值时记录（变快不报）。"""
    cfg = config or CONFIG
    base = {row.get("shape"): row for row in baseline}
    drifts: list[str] = []
    for row in measured:
        label = row.get("shape")
        ref = base.get(label)
        if ref is None:
            drifts.append(f"{label}: 基线缺少该形态")
            continue
        for key in TIMED_KEYS:
            cur_p50, _, cur_n = _metric_value(row.get(key))
            old_p50, _, _ = _metric_value(ref.get(key))
            if cur_p50 is None or old_p50 is None:
                drifts.append(f"{label}/{key}: 缺少 p50 计时")
                continue
            if cur_n == 0:
                drifts.append(f"{label}/{key}: 样本数为 0")
                continue
            if old_p50 <= 0:
                drifts.append(f"{label}/{key}: 基线 p50 非正，无法比较")
                continue
            delta = (float(cur_p50) - float(old_p50)) / float(old_p50)
            if delta > float(cfg["relative_band"]):
                drifts.append(
                    f"{label}/{key}: {float(cur_p50):.1f}ms vs 基线 {float(old_p50):.1f}ms"
                    f"（{delta:+.0%}，超出 +{float(cfg['relative_band']):.0%} 退化带）"
                )
        for key in MEMORY_KEYS:
            cur = row.get(key)
            old = ref.get(key)
            if not isinstance(cur, (int, float)) or not isinstance(old, (int, float)):
                drifts.append(
                    f"{label}/{key}: 缺少可比较的数值（当前 {type(cur).__name__}，"
                    f"基线 {type(old).__name__}）"
                )
                continue
            if float(old) <= 0:
                drifts.append(f"{label}/{key}: 基线值非正，无法比较")
                continue
            delta = (float(cur) - float(old)) / float(old)
            if delta > float(cfg["memory_band"]):
                drifts.append(
                    f"{label}/{key}: {float(cur):.3f}MB vs 基线 {float(old):.3f}MB"
                    f"（{delta:+.0%}，超出 +{float(cfg['memory_band']):.0%} 退化带）"
                )
        for key in SIZE_KEYS:
            cur = row.get(key)
            old = ref.get(key)
            if not isinstance(cur, (int, float)) or not isinstance(old, (int, float)):
                drifts.append(
                    f"{label}/{key}: 缺少可比较的数值（当前 {type(cur).__name__}，"
                    f"基线 {type(old).__name__}）"
                )
                continue
            if float(old) <= 0:
                drifts.append(f"{label}/{key}: 基线值非正，无法比较")
                continue
            delta = (float(cur) - float(old)) / float(old)
            if delta > float(cfg["size_band"]):
                drifts.append(
                    f"{label}/{key}: {float(cur):.0f}B vs 基线 {float(old):.0f}B"
                    f"（{delta:+.0%}，超出 +{float(cfg['size_band']):.0%} 退化带）"
                )
    return drifts


def _same_fingerprint(measured: dict, baseline: dict) -> tuple[bool, list[str]]:
    missing = [key for key in FINGERPRINT_KEYS if measured.get(key) is None or baseline.get(key) is None]
    if missing:
        return False, missing
    changed = []
    for key in FINGERPRINT_KEYS:
        if measured.get(key) != baseline.get(key):
            changed.append(key)
    return not changed, changed


def _exit_code(status: str) -> int:
    return int(CONFIG["exit_codes"].get(status, 1))


def _print_status(status: str, detail: str = "") -> None:
    suffix = f" {detail}" if detail else ""
    token = "ok" if status == "PASS" else status.lower()
    print(f"bench_regress: check={token} status={status}{suffix}")


def _run_check(args: argparse.Namespace) -> int:
    """CI 闸门：指纹 + 输入契约 + 线程配置全部相同才允许 PASS。"""
    baseline_path = Path(args.baseline)
    if not baseline_path.is_file():
        print(
            f"bench_regress: check=error status=ERROR 缺少基线 {baseline_path}；"
            "先运行 python tools/bench_regress.py --json "
            "docs/bench_baseline.json",
            file=sys.stderr,
        )
        return _exit_code("ERROR")
    try:
        baseline_doc = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"bench_regress: check=error status=ERROR 基线不可读：{exc}", file=sys.stderr)
        return _exit_code("ERROR")
    baseline_rows = baseline_doc.get("results")
    if not isinstance(baseline_rows, list) or not baseline_rows:
        print("bench_regress: check=error status=ERROR 基线 results 为空", file=sys.stderr)
        return _exit_code("ERROR")

    if args.input:
        input_path = Path(args.input)
        if not input_path.is_file():
            print(
                f"bench_regress: check=error status=ERROR 缺少测量结果 {input_path}",
                file=sys.stderr,
            )
            return _exit_code("ERROR")
        try:
            measured_doc = json.loads(input_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(
                f"bench_regress: check=error status=ERROR 测量结果不可读：{exc}",
                file=sys.stderr,
            )
            return _exit_code("ERROR")
        measured_rows = measured_doc.get("results")
        measured_fingerprint = {k: measured_doc.get(k) for k in FINGERPRINT_KEYS}
        measured_input = measured_doc.get("input_contract")
    else:
        shapes = [s.strip() for s in args.shapes.split(",") if s.strip()]
        measured_rows = [bench_shape(s) for s in shapes]
        measured_fingerprint = {k: v for k, v in _fingerprint().items() if k in FINGERPRINT_KEYS}
        measured_input = INPUT_CONTRACT

    if not isinstance(measured_rows, list) or not measured_rows:
        print("bench_regress: check=error status=ERROR 测量结果 results 为空", file=sys.stderr)
        return _exit_code("ERROR")

    ref_fingerprint = {k: baseline_doc.get(k) for k in FINGERPRINT_KEYS}
    same, changed = _same_fingerprint(measured_fingerprint, ref_fingerprint)
    input_same = baseline_doc.get("input_contract") == measured_input
    if not input_same:
        changed = [*changed, "input_contract"]
        same = False
    drifts = _compare(measured_rows, baseline_rows)
    if not same:
        for line in drifts:
            print(f"  [info] {line}")
        print(f"  指纹/输入契约不同：{', '.join(changed) or '未知字段'}；跨机或跨输入比较不可判定")
        _print_status("INCOMPARABLE", f"incomparable_fields={','.join(changed) or 'unknown'}")
        if getattr(args, "allow_incomparable", False):
            missing_fields = [
                key
                for key in FINGERPRINT_KEYS
                if measured_fingerprint.get(key) is None
                or ref_fingerprint.get(key) is None
            ]
            blockers = [
                key
                for key in [*changed, *missing_fields]
                if key not in SMOKE_TOLERATED_FINGERPRINT_KEYS
            ]
            if blockers:
                print(
                    "  [ci] --allow-incomparable 不能放行："
                    f"{', '.join(sorted(set(blockers)))} 变化不属于机器差异"
                )
                return _exit_code("INCOMPARABLE")
            # CI 共享 runner 无法与本地基线同指纹；显式放行但保留 INCOMPARABLE
            # 状态与字段差异，回归比较仍只在同指纹机器上执行。
            print("  [ci] --allow-incomparable：共享 runner 跳过跨机比较，本地严格闸门不变")
            return 0
        return _exit_code("INCOMPARABLE")
    for line in drifts:
        print(f"  [drift] {line}")
    if drifts:
        _print_status("DRIFT")
        return _exit_code("DRIFT")
    _print_status("PASS")
    return _exit_code("PASS")


def main() -> int:
    ap = argparse.ArgumentParser(description="PlotKit 性能回归基准")
    ap.add_argument("--json", default="", help="落盘机器结果 JSON（与基线同形）")
    ap.add_argument("--check", action="store_true", help="严格回归闸门（同指纹参考机器）")
    ap.add_argument("--shapes", default="sine,noise")
    ap.add_argument("--baseline", default=str(BASELINE), help="基线 JSON 路径")
    ap.add_argument(
        "--allow-incomparable",
        action="store_true",
        help="CI 共享 runner 专用：指纹不同时保留 INCOMPARABLE 输出但按 0 退出；默认仍为 2",
    )
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
        + "   p50/p95(ms)"
    )
    for key, label in keys:
        cells = [f"{_fmt(r[key]):>18s}" for r in rows]
        print(f"{label:30s} " + " ".join(cells))

    print("\n内存峰值（tracemalloc / RSS, MB）")
    for key, label in [
        ("downsample_2m_memory", "抽稀 2M"),
        ("append_memory", "追加 2000 次"),
        ("add_2m_memory", "入库 2M float64"),
    ]:
        print(f"  {label:16s} " + "  ".join(f"{r[key]['tracemalloc_peak_mb']:.1f}" for r in rows))

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
