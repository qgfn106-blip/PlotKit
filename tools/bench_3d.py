"""三维双后端基准（D38）。

用法：
    python tools/bench_3d.py            # 打印表格
    python tools/bench_3d.py --json     # 机器可读
    python tools/bench_3d.py --check    # 超预算返回非零（CI 用）

预算取自 docs/THREE_D_BACKENDS.md §8：三维 10 万点 / 1 万单元出图 ≤2s。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("MPLBACKEND", "Agg")

import plotkit as pk  # noqa: E402

BUDGET_MS = {"surface_100": 150.0, "scatter_100k": 400.0, "voxels_35": 400.0}


def _rss_mb() -> float | None:
    try:
        import psutil
    except Exception:
        return None
    try:
        proc = psutil.Process()
        total = proc.memory_info().rss
        for child in proc.children(recursive=True):
            try:
                total += child.memory_info().rss
            except Exception:
                pass
        return round(total / 1048576, 1)
    except Exception:
        return None


def _surface(points: int):
    x = np.linspace(-3, 3, points)
    y = np.linspace(-3, 3, points)
    X, Y = np.meshgrid(x, y)
    fig = pk.figure(title=f"surface {points}x{points}")
    fig.add("surface", {"x": X, "y": Y, "z": np.sin(np.hypot(X, Y))})
    return fig


def _scatter(n: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    fig = pk.figure(title=f"scatter3d {n}")
    fig.add("scatter3d", {"x": rng.normal(size=n), "y": rng.normal(size=n), "z": rng.normal(size=n)})
    return fig


def _voxels(n: int, seed: int = 0):
    rng = np.random.default_rng(seed)
    fig = pk.figure(title=f"voxels {n}^3")
    fig.add("voxels", {"z": rng.random((n, n, n))})
    return fig


CASES = [
    ("surface_30", lambda: _surface(30), 700, 450),
    ("surface_60", lambda: _surface(60), 700, 450),
    ("surface_100", lambda: _surface(100), 700, 450),
    ("scatter_10k", lambda: _scatter(10_000), 700, 450),
    ("scatter_100k", lambda: _scatter(100_000), 700, 450),
    ("voxels_15", lambda: _voxels(15), 700, 450),
    ("voxels_25", lambda: _voxels(25), 700, 450),
    ("voxels_35", lambda: _voxels(35), 800, 600),   # 文档 §8 的目标场景（mpl 侧要 14s，跑一次即可）
]


def _time_backend(fig, backend: str, width: int, height: int, repeats: int = 3) -> dict:
    """预热一次再计时（VTK 首次要建上下文，matplotlib 首次要加载字体）。"""
    try:
        fig.render_result(width=width, height=height, backend=backend)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:200]}
    times, size = [], 0
    for _ in range(repeats):
        t0 = time.perf_counter()
        result = fig.render_result(width=width, height=height, backend=backend)
        times.append((time.perf_counter() - t0) * 1000.0)
        size = len(result.payload)
    return {
        "ok": True,
        "p50_ms": round(float(np.median(times)), 1),
        "min_ms": round(float(min(times)), 1),
        "bytes": size,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="三维双后端基准")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--backend", default=None, help="只跑指定后端")
    args = parser.parse_args(argv)

    rss_start = _rss_mb()
    report: dict[str, dict] = {}
    for name, make, width, height in CASES:
        row: dict[str, object] = {}
        for backend in ("mpl", "pyvista"):
            if args.backend and backend != args.backend:
                continue
            fig = make()
            row[backend] = _time_backend(fig, backend, width, height)
        report[name] = row
    rss_end = _rss_mb()

    if args.json:
        print(json.dumps({"cases": report, "rss_mb": {"start": rss_start, "end": rss_end}},
                         ensure_ascii=False, indent=2))
    else:
        print(f"{'case':14s} {'mpl p50':>10s} {'pyvista p50':>12s} {'speedup':>8s}")
        for name, row in report.items():
            mpl = row.get("mpl") or {}
            pv = row.get("pyvista") or {}
            if mpl.get("ok") and pv.get("ok"):
                ratio = mpl["p50_ms"] / pv["p50_ms"] if pv["p50_ms"] else 0
                print(f"{name:14s} {mpl['p50_ms']:>9.0f}ms {pv['p50_ms']:>10.0f}ms {ratio:>7.1f}x")
            elif mpl.get("ok"):
                print(f"{name:14s} {mpl['p50_ms']:>9.0f}ms {'—':>12s}   ({pv.get('error', 'skipped')})")
            else:
                print(f"{name:14s} {'—':>10s} {'—':>12s}   ({mpl.get('error', 'skipped')})")
        print(f"RSS: {rss_start} MB -> {rss_end} MB")

    if args.check:
        failures = []
        for name, budget in BUDGET_MS.items():
            row = report.get(name) or {}
            pv = row.get("pyvista") or {}
            if not pv.get("ok"):
                failures.append(f"{name}: pyvista 不可用（{pv.get('error')}）")
            elif pv["p50_ms"] > budget:
                failures.append(f"{name}: {pv['p50_ms']}ms > 预算 {budget}ms")
        for line in failures:
            print("[FAIL]", line, file=sys.stderr)
        return 1 if failures else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
