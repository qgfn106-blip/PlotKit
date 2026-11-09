# -*- coding: utf-8 -*-
"""性能回归闸门的行为契约（裁定 ⑧-4）。

只通过公开 CLI ``tools/bench_regress.py --check`` 断言退出码与返回值约定，
不读源码字符串、不设任何毫秒硬阈值、不比较具体耗时数值。基线缺失时必须
响亮报错而非静默跳过。
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
        old = row["cold_png"][0]
        row["cold_png"] = [old * 100, old * 100]
    drift_input = tmp_path / "drift.json"
    drift_input.write_text(json.dumps(drifted, ensure_ascii=False), encoding="utf-8")
    drift = _run("--input", str(drift_input))
    assert drift.returncode != 0, drift.stdout + drift.stderr
    assert "bench_regress: check=drift" in drift.stdout

    # 基线缺失：必须非零且明确报出缺少基线，而不是 return 0 或跳过。
    missing = _run("--baseline", str(tmp_path / "no-baseline.json"))
    assert missing.returncode != 0
    assert "check=error" in (missing.stdout + missing.stderr)
    assert "缺少基线" in (missing.stdout + missing.stderr)
