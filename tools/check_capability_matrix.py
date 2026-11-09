#!/usr/bin/env python3
"""P0 能力矩阵闸门：校验 8 行契约、决策一致性与可观测降级。

验证 ``decision_report()`` 在 extras 全可用时逐行命中矩阵 backend；在 three/ns
缺失时要求依赖 extra 的行全部 degraded=True 且带 fallback。写出
reports/decisions.json（来自 decision_report()，顺序与矩阵一致）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from plotkit.backends.selector import capability_rows, decision_report  # noqa: E402

REPORT = ROOT / "reports" / "decisions.json"

# 裁定 ⑨-4：报告是「理想环境重放」，不是运行时采样；必须显式标注。
ENVIRONMENT = "all-extras-available (synthetic)"
ALL_EXTRAS: dict[str, bool] = {"three": True, "ns": True}

ROW_KEYS = (
    "id",
    "situation",
    "match",
    "backend",
    "placement",
    "capabilities_used",
    "fallback",
    "degraded_when",
    "acceptance",
)
MATCH_KEYS = ("doc_features", "target_kinds", "formats", "qualities", "requires_extra")


def evaluate(available: dict[str, bool] | None = None) -> tuple[dict, list[str]]:
    violations: list[str] = []
    raw_rows = capability_rows()
    rows: list[dict] = list(raw_rows) if isinstance(raw_rows, list) else []
    extras = ALL_EXTRAS if available is None else dict(available)
    report = decision_report(available=extras)
    payload = {
        "environment": ENVIRONMENT,
        "schema": "plotkit.decisions/v1",
        "rows": report,
    }

    if len(rows) != 8:
        violations.append(f"能力矩阵必须恰好 8 行，实际 {len(rows)}")

    ids: list[str] = []
    for index, row in enumerate(rows):
        missing = [key for key in ROW_KEYS if key not in row]
        if missing:
            violations.append(f"rows[{index}] 缺少字段 {', '.join(missing)}")
        ident = str(row.get("id") or "")
        ids.append(ident)
        if not ident:
            violations.append(f"rows[{index}] id 为空")
        if not row.get("backend"):
            violations.append(f"rows[{index}] backend 为空")
        if not row.get("acceptance"):
            violations.append(f"rows[{index}] acceptance 为空")
        match = row.get("match")
        if not isinstance(match, dict):
            violations.append(f"rows[{index}] match 必须是对象")
        else:
            absent = [key for key in MATCH_KEYS if key not in match]
            if absent:
                violations.append(f"rows[{index}].match 缺少字段 {', '.join(absent)}")
    if len(set(ids)) != len(ids):
        violations.append("能力矩阵 id 不唯一")

    if len(report) != 8:
        violations.append(f"decision_report() 必须返回 8 条，实际 {len(report)}")
    elif len(rows) == 8:
        for index, (row, entry) in enumerate(zip(rows, report)):
            if entry.get("id") != row.get("id"):
                violations.append(f"decision_report()[{index}] id 与矩阵顺序不一致")
            decision = entry.get("decision") or {}
            if decision.get("backend") != row.get("backend"):
                violations.append(
                    f"decision_report()[{index}] backend 与矩阵不一致（extras 全可用）"
                )
            if decision.get("degraded") is not False:
                violations.append(
                    f"decision_report()[{index}] 在 extras 全可用时仍标记 degraded"
                )
            if not entry.get("acceptance"):
                violations.append(f"decision_report()[{index}] acceptance 为空")

    degraded = decision_report(available={"three": False, "ns": False})
    degraded_ids = {
        str(entry.get("id"))
        for entry in degraded
        if (entry.get("decision") or {}).get("degraded") is True
    }
    expected = {
        str(row.get("id"))
        for row in rows
        if isinstance(row.get("match"), dict) and row["match"].get("requires_extra")
    }
    if not degraded_ids:
        violations.append("three/ns 缺失时未观察到任何降级决策")
    if expected and not expected <= degraded_ids:
        violations.append("three/ns 缺失时，依赖 extra 的能力行未全部降级")
    for entry in degraded:
        decision = entry.get("decision") or {}
        if decision.get("degraded") is True:
            if not decision.get("fallback"):
                violations.append(f"{entry.get('id')} 降级决策缺少 fallback")
            if not decision.get("backend"):
                violations.append(f"{entry.get('id')} 降级决策缺少 backend")

    return payload, sorted(set(violations))


def _write_report(payload: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    REPORT.write_text(text, encoding="utf-8")


def run(
    *,
    write: bool = True,
    quiet: bool = False,
    available: dict[str, bool] | None = None,
) -> int:
    payload, violations = evaluate(available=available)
    if write:
        _write_report(payload)
    elif REPORT.is_file():
        try:
            committed = json.loads(REPORT.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            violations.append(f"reports/decisions.json 无法读取：{exc}")
        else:
            if committed != payload:
                violations.append(
                    "reports/decisions.json 与当前矩阵不一致；"
                    "请重新运行 python tools/check_capability_matrix.py"
                )
    else:
        violations.append(
            "缺少 reports/decisions.json；请先运行 python tools/check_capability_matrix.py"
        )
    for item in violations:
        print(item, file=sys.stderr)
    if not quiet:
        print(
            f"check_capability_matrix: rows={len(payload['rows'])} "
            f"violations={len(violations)} ok={not violations}"
        )
    return 1 if violations else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PlotKit 能力矩阵闸门")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write", action="store_true", help="生成 reports/decisions.json（默认）"
    )
    mode.add_argument(
        "--check", action="store_true", help="只读核对已提交报告，不写文件"
    )
    args = parser.parse_args(argv)
    return run(write=not args.check)


if __name__ == "__main__":
    sys.exit(main())
