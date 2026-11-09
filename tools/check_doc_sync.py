#!/usr/bin/env python3
"""P0 文档 / 契约同步闸门：冻结规格、需求台账、package-data 与 schema $id。

并行任务可能正在写 docs/**，因此缺失或标记缺失时会短暂重试；重试后仍不成立
则给出带路径的明确错误并退出 1。写出 reports/schema.json（确定性 JSON）。
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from plotkit.backends.selector import capability_rows  # noqa: E402
from plotkit.schema import contract_hashes, load  # noqa: E402
from plotkit.store.frame import frame_schema_id  # noqa: E402

REPORT = ROOT / "reports" / "schema.json"
SPEC = ROOT / "docs" / "specs" / "2026-11-09-p0-contract-freeze.md"
PROGRESS = ROOT / "docs" / "REQUIREMENTS_AND_PROGRESS.md"
PYPROJECT = ROOT / "pyproject.toml"
FROZEN = ("figure.v1.json", "frame.v1.json", "capability.v1.json", "compat_matrix.json")

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback
    tomllib = None  # type: ignore[assignment]


def _rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _collect() -> tuple[dict, list[str]]:
    problems: list[str] = []

    if not SPEC.is_file():
        problems.append(f"缺少冻结规格：{_rel(SPEC)}（并行任务尚未生成？）")
    if not PROGRESS.is_file():
        problems.append(f"缺少需求台账：{_rel(PROGRESS)}")
    else:
        text = PROGRESS.read_text(encoding="utf-8")
        for marker in ("PK-R24", "D39"):
            if marker not in text:
                problems.append(f"{_rel(PROGRESS)} 缺少标记 {marker}")

    if not PYPROJECT.is_file():
        problems.append(f"缺少 {_rel(PYPROJECT)}")
    else:
        text = PYPROJECT.read_text(encoding="utf-8")
        if tomllib is not None:
            try:
                package_data = tomllib.loads(text)["tool"]["setuptools"][
                    "package-data"
                ]["plotkit"]
            except (KeyError, tomllib.TOMLDecodeError) as exc:
                problems.append(
                    f"{_rel(PYPROJECT)} 读取 package-data 失败：{type(exc).__name__}: {exc}"
                )
            else:
                if "schema/*.json" not in [str(item) for item in package_data]:
                    problems.append(
                        f"{_rel(PYPROJECT)} 的 package-data 未声明 schema/*.json"
                    )
        elif '"schema/*.json"' not in text:
            problems.append(f"{_rel(PYPROJECT)} 未声明 schema/*.json")

    figure_doc: dict = {}
    frame_doc: dict = {}
    capability_doc: dict = {}
    compat: dict = {}
    hashes: dict[str, str] = {}
    try:
        figure_doc = load("figure.v1.json")
        frame_doc = load("frame.v1.json")
        capability_doc = load("capability.v1.json")
        compat = load("compat_matrix.json")
        hashes = contract_hashes()
    except (OSError, ValueError, KeyError) as exc:
        problems.append(f"schema/*.json 契约读取失败：{type(exc).__name__}: {exc}")

    frame_id = frame_schema_id()
    versions = [str(item) for item in (compat.get("frame_schema_versions") or [])]
    if frame_doc.get("$id") != frame_id:
        problems.append(
            f"frame.v1.json 的 $id 与 frame_schema_id() 不一致："
            f"{frame_doc.get('$id')!r} != {frame_id!r}"
        )
    if frame_id not in versions:
        problems.append(
            f"compat_matrix.json 的 frame_schema_versions 未包含 {frame_id}"
        )
    if not figure_doc.get("$id"):
        problems.append("figure.v1.json 缺少 $id")
    if not capability_doc.get("$id"):
        problems.append("capability.v1.json 缺少 $id")
    absent = [name for name in FROZEN if name not in hashes]
    if absent:
        problems.append(f"contract_hashes() 缺少冻结契约：{', '.join(absent)}")

    n_rows = len(capability_rows())
    if n_rows != 8:
        problems.append(f"能力矩阵行数应为 8，实际 {n_rows}")

    payload = {
        "schema": "plotkit.schema_report/v1",
        "figure": {
            "$id": figure_doc.get("$id"),
            "sha256": hashes.get("figure.v1.json"),
        },
        "frame": {
            "$id": frame_doc.get("$id"),
            "sha256": hashes.get("frame.v1.json"),
        },
        "capability_rows": n_rows,
        "compat": {
            "$id": compat.get("schema") or compat.get("$id"),
            "sha256": hashes.get("compat_matrix.json"),
            "frame_schema_versions": sorted(versions),
            "contract_hashes": {
                name: hashes[name] for name in FROZEN if name in hashes
            },
        },
    }
    return payload, problems


def evaluate() -> tuple[dict, list[str]]:
    """Retry briefly so a concurrently written doc does not cause a false alarm."""
    payload, problems = _collect()
    for _ in range(5):
        if not problems:
            break
        time.sleep(0.1)
        payload, problems = _collect()
    return payload, sorted(set(problems))


def _write_report(payload: dict) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    REPORT.write_text(text, encoding="utf-8")


def run(*, write: bool = True, quiet: bool = False) -> int:
    payload, violations = evaluate()
    if write:
        _write_report(payload)
    elif REPORT.is_file():
        try:
            committed = json.loads(REPORT.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            violations.append(f"reports/schema.json 无法读取：{exc}")
        else:
            if committed != payload:
                violations.append(
                    "reports/schema.json 与当前契约不一致；"
                    "请重新运行 python tools/check_doc_sync.py"
                )
    else:
        violations.append(
            "缺少 reports/schema.json；请先运行 python tools/check_doc_sync.py"
        )
    for item in violations:
        print(item, file=sys.stderr)
    if not quiet:
        print(
            f"check_doc_sync: capability_rows={payload['capability_rows']} "
            f"violations={len(violations)} ok={not violations}"
        )
    return 1 if violations else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PlotKit 文档 / 契约同步闸门")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--write", action="store_true", help="生成 reports/schema.json（默认）"
    )
    mode.add_argument(
        "--check", action="store_true", help="只读核对已提交报告，不写文件"
    )
    args = parser.parse_args(argv)
    return run(write=not args.check)


if __name__ == "__main__":
    sys.exit(main())
