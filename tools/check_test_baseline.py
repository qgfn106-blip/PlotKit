#!/usr/bin/env python3
"""P0 G0 收集数常量门禁（裁定 ⑪ / R-b′ 加固版，基线 schema v2）。

判据（全部满足才 ok）：
  * ``collected == 钉定常量``（reports/test_baseline.json 的 collected，本轮 544）
  * ``failed == 0``（failed + error + errors）
  * ``collected == passed + failed + skipped``（计入 failed，修掉旧公式的伪 violation）
  * skipped 的**用例集合与总数**都与所选 profile 的基线一致
  * 出现 xfailed / xpassed / deselected 视为违规
  * pytest 退出码 == 0

环境指纹 = python(主.次) + os(platform.system()) + extras 五件的 find_spec 布尔
（extras = pyvista / vtk / psutil / pywebview / h5py）。基线 v2 可按指纹存多个 profile，
当前环境必须**精确匹配**某个 profile，否则报错（禁止静默回退）。任何 collected 下降
都要求 docs/waivers.md 事前豁免。

用法：
  python tools/check_test_baseline.py                     # 校验（CI step 使用）
  python tools/check_test_baseline.py --write KEY [--python 3.11 --os Linux --extras none]
                                                          # 机器化生成/更新某 profile（禁止手写）
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "reports" / "test_baseline.json"
WAIVER_HINT = "需 docs/waivers.md 事前豁免"
SCHEMA = "plotkit.test_baseline/v2"
EXTRAS = ("pyvista", "vtk", "psutil", "pywebview", "h5py")

# 收集阶段：只收集、不执行，避免把「测试数」与「通过数」混为一谈。
COLLECT_CMD = [
    sys.executable, "-m", "pytest", "-o", "addopts=", "--collect-only", "-q",
]
# 全量阶段：-ra 让跳过项以 SKIPPED 行显式列出（集合与计数都可核对）。
SUITE_CMD = [
    sys.executable, "-m", "pytest", "-o", "addopts=", "-q", "--disable-warnings", "-ra",
]

_COUNT_RE = re.compile(
    r"(\d+)\s+(passed|failed|error|errors|skipped|xfailed|xpassed|"
    r"deselected|warning|warnings)\b"
)
_COLLECTED_RE = re.compile(r"(\d+)\s+tests?\s+collected\b")
_SKIPPED_RE = re.compile(r"^SKIPPED\s+\[(\d+)\]\s+(.+?):\s", re.MULTILINE)


def _env() -> dict[str, str]:
    env = dict(os.environ)
    src = str(ROOT / "src")
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = src + (os.pathsep + existing if existing else "")
    return env


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd, cwd=ROOT, env=_env(), capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )


def _counts(text: str) -> dict[str, int]:
    found: dict[str, int] = {}
    for number, label in _COUNT_RE.findall(text):
        found[label] = int(number)
    return found


def _collected(text: str) -> int | None:
    matches = _COLLECTED_RE.findall(text)
    return int(matches[-1]) if matches else None


def _skipped_entries(text: str) -> list[tuple[str, int]]:
    """返回 (path:line, n)：n 是该位置跳过的用例数（参数化同处多行共享一个位置）。"""
    return [(loc.replace("\\", "/"), int(n)) for n, loc in _SKIPPED_RE.findall(text)]


def _skipped_ids(text: str) -> list[str]:
    return sorted({loc for loc, _ in _skipped_entries(text)})


def _skipped_total(text: str) -> int:
    return sum(n for _, n in _skipped_entries(text))


def _extra_present(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def current_fingerprint() -> dict:
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "os": platform.system(),
        "extras": {name: _extra_present(name) for name in EXTRAS},
    }


def _match_profile(baseline: dict, fp: dict) -> tuple[str | None, dict | None]:
    for key, prof in (baseline.get("profiles") or {}).items():
        if prof.get("environment_fingerprint") == fp:
            return key, prof
    return None, None


def _load() -> dict:
    if not BASELINE.is_file():
        raise FileNotFoundError(f"缺少基线文件 {BASELINE}")
    return json.loads(BASELINE.read_text(encoding="utf-8"))


def evaluate() -> tuple[dict, list[str], int]:
    violations: list[str] = []
    try:
        baseline = _load()
    except Exception as exc:  # noqa: BLE001
        return {}, [f"无法读取基线 {BASELINE}: {exc}"], 1
    if baseline.get("schema") != SCHEMA:
        return {}, [
            f"基线 schema 必须是 {SCHEMA}，实际 {baseline.get('schema')!r}"
            "（运行 --write 升级，禁止沿用 v1 的 collected/skipped 平铺结构）"
        ], 1
    pinned = baseline.get("collected")
    if not isinstance(pinned, int) or isinstance(pinned, bool) or pinned <= 0:
        return {}, [f"基线 collected 必须是正整数，实际 {pinned!r}"], 1

    fp = current_fingerprint()
    key, profile = _match_profile(baseline, fp)
    if profile is None:
        return {"fingerprint": fp}, [
            "环境指纹不匹配任何基线 profile —— 不得静默回退；"
            f"当前={json.dumps(fp, ensure_ascii=False, sort_keys=True)}，"
            f"已有 profile={list((baseline.get('profiles') or {}).keys())}。"
            "请运行 `python tools/check_test_baseline.py --write <key>` 生成并复核。"
        ], 1

    expected_ids = sorted(set(profile.get("skipped_ids") or []))
    expected_total = int(profile.get("skipped_total", len(expected_ids)))

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
    got_ids = _skipped_ids(suite_text)
    got_total = _skipped_total(suite_text)

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
                "复核后更新 reports/test_baseline.json（禁止放宽为下限）"
            )
    if collected != passed + failed + skipped:
        violations.append(
            "collected == passed + failed + skipped 不满足："
            f"{collected} != {passed} + {failed} + {skipped}（counts={counts}）"
        )
    for extra in ("xfailed", "xpassed", "deselected"):
        if counts.get(extra):
            violations.append(f"出现 {extra}={counts[extra]}（不允许隐藏/丢弃用例）")
    if got_ids != expected_ids:
        missing = [x for x in expected_ids if x not in got_ids]
        unexpected = [x for x in got_ids if x not in expected_ids]
        violations.append(
            f"skipped 集合与 profile[{key}] 不一致：缺 {missing[:8]} 多 {unexpected[:8]}"
        )
    if got_total != expected_total:
        violations.append(
            f"skipped 总数与 profile[{key}] 不一致：{got_total} != {expected_total}"
        )

    payload = {
        "ok": not violations,
        "profile": key,
        "fingerprint": fp,
        "collected": collected,
        "pinned": pinned,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "skipped_total": got_total,
        "skipped_locations": len(got_ids),
        "violations": violations,
    }
    return payload, violations, (0 if not violations else 1)


def write_profile(key: str, python: str | None, os_name: str | None, extras: str | None) -> None:
    fp = current_fingerprint()
    if python:
        fp["python"] = python
    if os_name:
        fp["os"] = os_name
    if extras in ("none", "all"):
        fp["extras"] = {name: (extras == "all") for name in EXTRAS}

    collect_proc = _run(COLLECT_CMD)
    collected = _collected((collect_proc.stdout or "") + (collect_proc.stderr or ""))
    suite_proc = _run(SUITE_CMD)
    suite_text = (suite_proc.stdout or "") + (suite_proc.stderr or "")
    counts = _counts(suite_text)
    failed = counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0)
    ids = _skipped_ids(suite_text)
    total = _skipped_total(suite_text)
    assert collected is not None, "无法解析 collected"
    assert failed == 0, f"--write 要求当前环境 failed==0，实际 failed={failed}（先修好再写基线）"

    try:
        baseline = _load()
    except FileNotFoundError:
        baseline = {"schema": SCHEMA, "collected": collected, "profiles": {}}
    baseline["schema"] = SCHEMA
    baseline["collected"] = collected
    baseline.setdefault("profiles", {})[key] = {
        "environment_fingerprint": fp,
        "skipped_ids": ids,
        "skipped_total": total,
    }
    BASELINE.write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"write_profile[{key}]: collected={collected} skipped_total={total} "
        f"skipped_locations={len(ids)}"
    )
    print(f"  fingerprint={json.dumps(fp, ensure_ascii=False, sort_keys=True)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G0 collected-count gate (baseline v2)")
    parser.add_argument("--write", metavar="KEY", help="生成/更新某环境 profile（机器化，禁止手写）")
    parser.add_argument("--python", help="--write 时覆盖 python 主.次（如 3.11）")
    parser.add_argument("--os", dest="os_name", help="--write 时覆盖 os（如 Linux / Windows）")
    parser.add_argument(
        "--extras", choices=["auto", "none", "all"], default="auto",
        help="--write 时覆盖 extras 向量：auto=按当前 find_spec",
    )
    args = parser.parse_args(argv)
    if args.write:
        write_profile(
            args.write, args.python, args.os_name,
            None if args.extras == "auto" else args.extras,
        )
        return 0
    payload, violations, code = evaluate()
    print(
        "check_test_baseline: "
        f"profile={payload.get('profile')} collected={payload.get('collected')} "
        f"pinned={payload.get('pinned')} passed={payload.get('passed')} "
        f"failed={payload.get('failed')} skipped={payload.get('skipped')} "
        f"skipped_total={payload.get('skipped_total')} exit={code} ok={payload.get('ok')}"
    )
    for item in violations:
        print("  " + item, file=sys.stderr)
        # GitHub Actions 注解：无需 token 也能从 check-runs annotations 读到具体违规
        print(f"::error::{item}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
