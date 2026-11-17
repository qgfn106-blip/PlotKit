# -*- coding: utf-8 -*-
"""PlotKit 渲染分层基准：完整重建 vs 复用 artist。

与 tools/bench_regress.py 的产品路径基准互补：本工具把渲染层的「重建构图」
与「复用 artist + draw」拆开，固定 1200x700@100dpi、6 通道、seed=1234、
预热/重复次数，报告 p50/p95/min/max/样本数与内存峰值。

用法：
    python tools/bench_layers.py
    python tools/bench_layers.py --unknowns 100 500 1000 5000
    python tools/bench_layers.py --check --baseline docs/bench_layers_baseline.json
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import matplotlib

matplotlib.use("Agg")

import bench_render as br  # noqa: E402
from evidence import environment, make_result, repository, write_result  # noqa: E402

WARM, REPEAT = 2, 5
DEFAULT_POINTS = (100, 500, 1000, 5000)
BASELINE = ROOT / "docs" / "bench_layers_baseline.json"
CONFIG_PATH = ROOT / "docs" / "bench_config.json"


def _load_config() -> dict:
    defaults = {"relative_band": 1.0, "memory_band": 0.5,
                "exit_codes": {"PASS": 0, "DRIFT": 1, "INCOMPARABLE": 2, "ERROR": 3}}
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return defaults
    if isinstance(raw, dict):
        for key in ("relative_band", "memory_band"):
            value = raw.get(key)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                defaults[key] = float(value)
        codes = raw.get("exit_codes")
        if isinstance(codes, dict):
            for status in ("PASS", "DRIFT", "INCOMPARABLE", "ERROR"):
                if isinstance(codes.get(status), int):
                    defaults["exit_codes"][status] = codes[status]
    return defaults


CONFIG = _load_config()


def _percentile(samples: list[float], fraction: float) -> float:
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


def _summary(samples: list[float]) -> dict:
    clean = [float(v) for v in samples if math.isfinite(float(v))]
    if not clean:
        return {"unit": "ms", "n": 0, "samples": [], "p50": None, "p95": None,
                "min": None, "max": None, "mean": None, "stdev": None}
    return {
        "unit": "ms", "n": len(clean), "samples": [round(v, 6) for v in clean],
        "p50": round(statistics.median(clean), 6), "p95": round(_percentile(clean, 0.95), 6),
        "min": round(min(clean), 6), "max": round(max(clean), 6),
        "mean": round(statistics.fmean(clean), 6),
        "stdev": round(statistics.pstdev(clean), 6) if len(clean) > 1 else 0.0,
    }


def _time(fn, warm: int = WARM, repeat: int = REPEAT) -> dict:
    for _ in range(max(0, warm)):
        fn()
    samples = []
    for _ in range(max(1, repeat)):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000.0)
    return _summary(samples)


def _rss_mb():
    try:
        import psutil  # type: ignore

        return round(psutil.Process(os.getpid()).memory_info().rss / 1e6, 3)
    except Exception:
        return None


def _peak_memory(fn) -> dict:
    before = _rss_mb()
    tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        fn()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    after = _rss_mb()
    return {
        "tracemalloc_peak_mb": round(peak / 1024 / 1024, 3),
        "rss_before_mb": before,
        "rss_after_mb": after,
        "rss_delta_mb": round(after - before, 3) if before is not None and after is not None else None,
        "peak_rss_mb": round(max(before, after), 3) if before is not None and after is not None else None,
    }


def bench_rendering(points: int, steps: int, warmup: int) -> list[dict]:
    t, ys = br._data(n=points, seed=1234)
    fig, canvas, ax, lines = br.build_figure(t, ys)
    canvas.draw()
    state = {"k": 0}

    def rebuild():
        fig2, canvas2, ax2, lines2 = br.build_figure(t, ys)
        canvas2.draw()

    def reuse():
        for line, y in zip(lines, ys):
            line.set_ydata(y * (1 + 0.01 * state["k"]))
        ax.set_xlim(0, 5)
        canvas.draw()
        state["k"] = (state["k"] + 1) % 50

    rows = []
    for case, fn in (("rendering_rebuild", rebuild), ("rendering_reuse", reuse)):
        timing = _time(fn, warm=warmup, repeat=steps)
        rows.append({
            "layer": "rendering",
            "case": case,
            "requested_unknowns": points,
            "nodes": 0,
            "edges": 0,
            "matrix_unknowns": None,
            "points": points,
            "channels": len(ys),
            "status": "PASS",
            "timing": timing,
            "steps": steps,
            "memory": _peak_memory(fn),
        })
    return rows


def run(args) -> tuple[dict, int]:
    started = time.perf_counter()
    started_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    points = list(args.unknowns or args.points or DEFAULT_POINTS)
    rows = []
    for size in points:
        rows.extend(bench_rendering(size, args.steps, args.warmup))
    exit_code = 0
    result = make_result(
        "tools/bench_layers.py", ROOT, sys.argv, exit_code,
        int((time.perf_counter() - started) * 1000), "passed",
        details={"config": {"unknowns": points, "steps": args.steps, "warmup": args.warmup,
                            "seed": 1234, "channels": 6, "resolution": "1200x700@100dpi"},
                 "results": rows},
        started_at=started_at,
    )
    result["schema_bench"] = "plotkit-bench-layers/1"
    result["environment_bench"] = environment()
    result["repository_bench"] = repository(ROOT)
    result["config"] = {"runner_version": "plotkit-bench-layers/1", "unknowns": points,
                        "steps": args.steps, "warmup": args.warmup, "seed": 1234,
                        "channels": 6, "resolution": "1200x700@100dpi", "backend": "Agg"}
    result["results"] = rows
    return result, exit_code


def _check(result: dict, baseline: dict) -> tuple[str, list[str]]:
    measured_env = result.get("environment_bench") or {}
    base_env = baseline.get("environment_bench") or {}

    def value(env, key):
        if key.startswith("packages."):
            return (env.get("packages") or {}).get(key.split(".", 1)[1])
        return env.get(key)

    changed = [key for key in ("processor", "machine", "cpu_count", "os", "os_release",
                               "python", "python_implementation", "packages.numpy",
                               "packages.scipy", "packages.matplotlib", "threads")
               if value(measured_env, key) != value(base_env, key)]
    if result.get("config") != baseline.get("config"):
        changed.append("config")
    if changed:
        return "INCOMPARABLE", [f"指纹/输入契约不同：{', '.join(changed)}"]
    base = {(r.get("case"), r.get("requested_unknowns")): r for r in baseline.get("results", [])}
    drifts = []
    for row in result.get("results", []):
        ref = base.get((row.get("case"), row.get("requested_unknowns")))
        if not ref:
            continue
        cur = (row.get("timing") or {}).get("p50")
        old = (ref.get("timing") or {}).get("p50")
        if not isinstance(cur, (int, float)) or not isinstance(old, (int, float)) or old <= 0:
            continue
        delta = (float(cur) - float(old)) / float(old)
        if delta > float(CONFIG["relative_band"]):
            drifts.append(f"{row['case']}/{row['requested_unknowns']}: {cur:.3f}ms vs {old:.3f}ms ({delta:+.0%})")
    return ("DRIFT", drifts) if drifts else ("PASS", [])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PlotKit 渲染分层基准")
    parser.add_argument("--unknowns", type=int, nargs="+", default=list(DEFAULT_POINTS))
    parser.add_argument("--points", type=int, nargs="+", default=None)
    parser.add_argument("--steps", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--out", default="reports/bench_layers.json")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--baseline", default=str(BASELINE))
    args = parser.parse_args(argv)

    result, _ = run(args)
    if args.check:
        path = Path(args.baseline)
        if not path.is_file():
            print(f"bench_layers: check=error status=ERROR 缺少基线 {path}")
            return 3
        try:
            baseline = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            print(f"bench_layers: check=error status=ERROR 基线不可读：{exc}")
            return 3
        status, details = _check(result, baseline)
        for line in details:
            print(f"  [{'drift' if status == 'DRIFT' else 'info'}] {line}")
        token = "ok" if status == "PASS" else status.lower()
        print(f"bench_layers: check={token} status={status}")
        return CONFIG["exit_codes"].get(status, 1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_result(out, result)
    print(f"bench_layers: status={result['status']} results={len(result['results'])} -> {out}")
    for row in result["results"]:
        timing = row.get("timing") or {}
        print(f"  {row['case']:20s} points={row['points']:<5d} p50={timing.get('p50')} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
