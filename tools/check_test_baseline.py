#!/usr/bin/env python3
"""P0 G0 收集数常量门禁（裁定 ⑪，取代旧的「通过数下限」镜像漏洞）。

判据：``collected == reports/test_baseline.json 钉定常量`` 且 ``failed == 0``
且 ``skipped`` 显式列出并与基线一致、``collected == passed + skipped``、
pytest ``exit 0``。任何 collected 下降都要求 ``docs/waivers.md`` 事前豁免。

四次全量/收集运行由本工具内部完成；其余 G0 条件（四门禁 violations == 0、
reports/*.json 二次生成 sha256 不变）由 CI 后续各 step 分别保证。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "reports" / "test_baseline.json"
WAIVER_HINT = "需 docs/waivers.md 事前豁免"

# 收集阶段：只收集、不执行，避免把「测试数」与「通过数」混为一谈。
COLLECT_CMD = [
    sys.executable,
    "-m",
    "pytest",
    "-o",
    "addopts=",
    "--collect-only",
    "-q",
]
# 全量阶段：-ra 让跳过项以 SKIPPED 行显式列出（skipped 集合可核对）。
SUITE_CMD = [
    sys.executable,
    "-m",
    "pytest",
    "-o",
    "addopts=",
    "-q",
    "--disable-warnings",
    "-ra",
]

_COUNT_RE = re.compile(
    r"(\d+)\s+(passed|failed|error|errors|skipped|xfailed|xpassed|"
    r"deselected|warning|warnings)\b"
)
_COLLECTED_RE = re.compile(r"(\d+)\s+tests?\s+collected\b")
_SKIPPED_RE = re.compile(r"^SKIPPED\s+\[\d+\]\s+(.+?):\s", re.MULTILINE)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    src = str(ROOT / "src")
    env["PYTHONPATH"] = src + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    return env


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _counts(text: str) -> dict[str, int]:
    """Parse the final pytest summary line(s); last occurrence wins per key."""
    found: dict[str, int] = {}
    for number, label in _COUNT_RE.findall(text):
        found[label] = int(number)
    return found


def _collected(text: str) -> int | None:
    matches = _COLLECTED_RE.findall(text)
    return int(matches[-1]) if matches else None


def _skipped_ids(text: str) -> list[str]:
    return sorted(set(_SKIPPED_RE.findall(text)))


def evaluate() -> tuple[dict, list[str], int]:
    violations: list[str] = []
    if not BASELINE.is_file():
        return {}, [f"缺少基线文件 {BASELINE}"], 0
    try:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {}, [f"无法读取基线 {BASELINE}: {exc}"], 0

    pinned = baseline.get("collected")
    expected_skipped = sorted(set(str(item) for item in baseline.get("skipped", [])))
    if not isinstance(pinned, int) or isinstance(pinned, bool) or pinned <= 0:
        return {}, [f"基线 collected 必须是正整数，实际 {pinned!r}"], 0

    collect_proc = _run(COLLECT_CMD)
    collected = _collected((collect_proc.stdout or "") + (collect_proc.stderr or ""))
    if collect_proc.returncode != 0:
        violations.append(f"--collect-only 退出码 {collect_proc.returncode} != 0")
    if collected is None:
        violations.append("无法从 --collect-only 输出解析 `N tests collected`")
        collected = 0

    suite_proc = _run(SUITE_CMD)
    suite_text = (suite_proc.stdout or "") + (suite_proc.stderr or "")
    counts = _counts(suite_text)
    passed = counts.get("passed", 0)
    failed = counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)
    skipped = counts.get("skipped", 0)
    skipped_ids = _skipped_ids(suite_text)

    if suite_proc.returncode != 0:
        violations.append(f"全量 pytest 退出码 {suite_proc.returncode} != 0")
    if failed:
        violations.append(f"failed == 0 不满足：failed={failed}")
    if collected != pinned:
        if collected < pinned:
            violations.append(f"collected 下降 {pinned} -> {collected}；{WAIVER_HINT}")
        else:
            violations.append(
                f"collected={collected} 与钉定常量 {pinned} 不一致；"
                f"复核后更新 reports/test_baseline.json（禁止放宽为下限）"
            )
    if collected != passed + skipped:
        violations.append(
            f"collected == passed + skipped 不满足："
            f"{collected} != {passed} + {skipped}（counts={counts}）"
        )
    for extra in ("xfailed", "xpassed", "deselected"):
        if counts.get(extra):
            violations.append(f"出现未计入判据的 {extra}={counts[extra]}")
    if skipped != len(expected_skipped):
        violations.append(
            f"skipped 数量与基线不一致：实跑 {skipped}，基线 {expected_skipped}"
        )
    elif skipped_ids and skipped_ids != expected_skipped:
        violations.append(
            f"skipped 集合与基线不一致：实跑 {skipped_ids}，" f"基线 {expected_skipped}"
        )

    payload = {
        "collected": collected,
        "pinned": pinned,
        "passed": passed,
        "failed": failed,
        "skipped": skipped_ids,
        "exit": suite_proc.returncode,
        "ok": not violations,
    }
    return payload, violations, 1 if violations else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="额外打印机器可读的门禁摘要")
    args = ap.parse_args(argv)
    payload, violations, code = evaluate()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    print(
        "check_test_baseline: "
        f"collected={payload.get('collected')} "
        f"pinned={payload.get('pinned')} "
        f"passed={payload.get('passed')} "
        f"failed={payload.get('failed')} "
        f"skipped={len(payload.get('skipped', []))} "
        f"exit={payload.get('exit')} "
        f"ok={payload.get('ok')}"
    )
    for item in violations:
        print("  " + item, file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
