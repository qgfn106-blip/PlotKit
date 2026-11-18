# -*- coding: utf-8 -*-
"""性能回归闸门的行为契约（裁定 ⑧-4）。

只通过公开 CLI ``tools/bench_regress.py --check`` 断言退出码与返回值约定，
不读源码字符串、不设任何毫秒硬阈值、不比较具体耗时数值。基线缺失时必须
响亮报错而非静默跳过。WP-4 追加四态：PASS / DRIFT / INCOMPARABLE / ERROR。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "bench_regress.py"
BASELINE = ROOT / "docs" / "bench_baseline.json"


def _run(*extra: str) -> subprocess.CompletedProcess[str]:
    # 子进程固定 UTF-8 输出，避免 Windows 控制台代码页把中文报错变成乱码。
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    return subprocess.run(
        [sys.executable, str(TOOL), "--check", *extra],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _p50(metric) -> float:
    """兼容统计 dict 与旧 [p50, min] 列表。"""
    if isinstance(metric, dict):
        return float(metric["p50"])
    return float(metric[0])


def test_bench_regress_check_exit_code_contract(tmp_path: Path) -> None:
    # 基线本身是闸门的数据契约；缺失时 --check 必须响亮报错，禁止静默跳过。
    assert BASELINE.is_file(), f"缺少性能基线 {BASELINE}；--check 必须失败而非跳过"
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))

    # 自比对：相对回归带内 → 约定为 check=ok / 退出码 0。
    ok = _run("--input", str(BASELINE))
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert "bench_regress: check=ok" in ok.stdout

    # 超带：由基线数值自身放大（不引入任何具体毫秒常量）→ check=drift / 非零。
    drifted = json.loads(json.dumps(baseline))
    for row in drifted["results"]:
        old = _p50(row["cold_png"])
        row["cold_png"] = {"p50": old * 100, "p95": old * 100, "n": 1, "samples": [old * 100]}
    drift_input = tmp_path / "drift.json"
    drift_input.write_text(json.dumps(drifted, ensure_ascii=False), encoding="utf-8")
    drift = _run("--input", str(drift_input))
    assert drift.returncode != 0, drift.stdout + drift.stderr
    assert "bench_regress: check=drift" in drift.stdout
    assert "status=DRIFT" in drift.stdout

    # 硬件指纹不同：即使计时相同也必须 INCOMPARABLE，禁止跨机误判 PASS。
    incompatible = json.loads(json.dumps(baseline))
    incompatible["cpu"] = "different-cpu"
    incompatible_input = tmp_path / "incomparable.json"
    incompatible_input.write_text(json.dumps(incompatible, ensure_ascii=False), encoding="utf-8")
    incomparable = _run("--input", str(incompatible_input))
    assert incomparable.returncode != 0, incomparable.stdout + incomparable.stderr
    assert "bench_regress: check=incomparable" in incomparable.stdout
    assert "status=INCOMPARABLE" in incomparable.stdout

    # CI 共享 runner 只能显式放行；状态与差异仍必须打印，本地默认仍为非零。
    allowed = _run("--input", str(incompatible_input), "--allow-incomparable")
    assert allowed.returncode == 0, allowed.stdout + allowed.stderr
    assert "status=INCOMPARABLE" in allowed.stdout
    assert "[ci] --allow-incomparable" in allowed.stdout

    # 基线缺失：必须非零且明确报出缺少基线，而不是 return 0 或跳过。
    missing = _run("--baseline", str(tmp_path / "no-baseline.json"))
    assert missing.returncode != 0
    assert "check=error" in (missing.stdout + missing.stderr)
    assert "缺少基线" in (missing.stdout + missing.stderr)


def test_bench_regress_report_has_distribution_and_memory_fields() -> None:
    """WP-4 验收：报告 p50/p95/min/max、样本数、RSS/峰值内存与分布。"""
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert baseline["schema"] == "plotkit-bench/2"
    for key in (
        "runner_version", "cpu", "machine", "cpu_count", "os", "os_release",
        "python", "numpy", "scipy", "matplotlib", "backend", "resolution",
        "blas", "mkl", "threads", "input_contract_sha256",
    ):
        assert key in baseline, key
    for row in baseline["results"]:
        metric = row["cold_png"]
        assert {"p50", "p95", "min", "max", "n", "samples", "stdev"} <= set(metric)
        memory = row["downsample_2m_memory"]
        assert {"tracemalloc_peak_mb", "peak_rss_mb"} <= set(memory)
