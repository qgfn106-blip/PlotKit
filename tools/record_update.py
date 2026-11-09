# -*- coding: utf-8 -*-
"""README「最近更新」块 与 docs/UPDATE_LOG.md 台账的一致性工具（裁定 E）。

README 标记块（固定五行 = 4 字段 + 完整记录链接）::
    <!-- UPDATE:LATEST:BEGIN -->
    - 日期：2026-11-09
    - 版本/ref：p0-freeze-2026-11-09
    - 更新内容：P0 契约冻结
    - 证据：docs/specs/2026-11-09-p0-contract-freeze.md
    - 完整记录：[docs/UPDATE_LOG.md](docs/UPDATE_LOG.md)
    <!-- UPDATE:LATEST:END -->

UPDATE_LOG.md 表格（固定表头，最多 10 行数据）::
    | # | 日期 | 版本/ref | 更新内容 | 证据 |
    | --- | --- | --- | --- | --- |
    | 1 | 2026-11-09 | p0-freeze-2026-11-09 | P0 契约冻结 | docs/... |

``--check`` 只读校验；``--add`` 在表头插入新行并重排编号，随后只重写
README 标记块内部与台账数据行，标记块外的所有内容原样保留。
仅用标准库；UTF-8 无 BOM；不修改 README.md / UPDATE_LOG.md 之外的文件。
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
UPDATE_LOG = ROOT / "docs" / "UPDATE_LOG.md"

BEGIN = "<!-- UPDATE:LATEST:BEGIN -->"
END = "<!-- UPDATE:LATEST:END -->"
HEADER = "| # | 日期 | 版本/ref | 更新内容 | 证据 |"
SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

FIELDS = ("日期", "版本/ref", "更新内容", "证据")
LABELS = ("- 日期：", "- 版本/ref：", "- 更新内容：", "- 证据：")
# 用户规则（2026-11-09）：README 除「最近一次更新」四字段外，必须保留一条指向
# 完整台账的直达链接，才能「保留最近十次的更新记录可查阅」。该行是固定 footer，
# 不是可变字段：--check 校验它存在，--add 重写块时原样带上。
RECORD_LINK_LABEL = "- 完整记录："
RECORD_LINK = "- 完整记录：[docs/UPDATE_LOG.md](docs/UPDATE_LOG.md)"
MAX_ROWS = 10


def _block_text(fields: dict[str, str]) -> str:
    """生成标记块内部文本（4 字段 + 固定链接行，前后各一个换行）。"""
    lines = [f"{label}{fields[field]}" for label, field in zip(LABELS, FIELDS)]
    lines.append(RECORD_LINK)
    return "\n" + "\n".join(lines) + "\n"


def _parse_block(text: str, violations: list[str]) -> dict[str, str] | None:
    if BEGIN not in text:
        violations.append(f"README 缺少起始标记 {BEGIN}")
        return None
    if END not in text:
        violations.append(f"README 缺少结束标记 {END}")
        return None
    start = text.index(BEGIN) + len(BEGIN)
    try:
        end = text.index(END, start)
    except ValueError:
        violations.append("README 标记顺序错误：END 出现在 BEGIN 之前")
        return None
    lines = [line.strip() for line in text[start:end].splitlines() if line.strip()]
    # 标记块 = 4 个可变字段行 + 1 条固定「完整记录」链接行（可查阅入口）。
    expected = len(FIELDS) + 1
    if len(lines) != expected:
        violations.append(
            f"README 标记块必须恰好 {expected} 行"
            f"（{len(FIELDS)} 字段 + 完整记录链接），实际 {len(lines)} 行"
        )
        return None
    tail = lines[-1]
    if not tail.startswith(RECORD_LINK_LABEL) or "docs/UPDATE_LOG.md" not in tail:
        violations.append(
            f"README 标记块末行必须是完整记录链接（形如 {RECORD_LINK!r}），"
            f"实际 {tail!r}"
        )
        return None
    fields: dict[str, str] = {}
    for label, field, line in zip(LABELS, FIELDS, lines[: len(FIELDS)]):
        if not line.startswith(label):
            violations.append(f"README 标记块第 {len(fields) + 1} 行应以 {label} 开头")
            continue
        fields[field] = line[len(label) :].strip()
    if len(fields) != len(FIELDS):
        return None
    for field in FIELDS:
        if not fields[field]:
            violations.append(f"README 标记块字段「{field}」为空")
    return fields


def _cells(line: str) -> list[str]:
    parts = [cell.strip() for cell in line.strip().split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _row_line(row: dict[str, str]) -> str:
    values = [str(row["#"])] + [row[field] for field in FIELDS]
    return "| " + " | ".join(values) + " |"


def _parse_table(
    text: str, violations: list[str]
) -> tuple[list[dict[str, str]], dict[str, object]] | None:
    """返回 (数据行, 位置信息)；位置信息供 --add 精确重写数据行。"""
    lines = text.splitlines()
    header_idx = next(
        (i for i, line in enumerate(lines) if line.strip() == HEADER), None
    )
    if header_idx is None:
        violations.append(f"UPDATE_LOG 缺少固定表头 {HEADER}")
        return None
    sep_idx = header_idx + 1
    if sep_idx >= len(lines) or not SEPARATOR_RE.match(lines[sep_idx].strip()):
        violations.append("UPDATE_LOG 表头下一行必须是 | --- | ... | 分隔行")
        return None
    first_data = sep_idx + 1
    data_end = first_data
    while data_end < len(lines) and lines[data_end].lstrip().startswith("|"):
        data_end += 1

    rows: list[dict[str, str]] = []
    for offset, line in enumerate(lines[first_data:data_end]):
        parts = _cells(line)
        if len(parts) != 5:
            violations.append(
                f"UPDATE_LOG 第 {offset + 1} 条数据行列数应为 5，实际 {len(parts)}"
            )
            continue
        rows.append({"#": parts[0], **dict(zip(FIELDS, parts[1:]))})
    info: dict[str, object] = {
        "lines": lines,
        "first_data": first_data,
        "data_end": data_end,
        "trailing": "\n" if text.endswith("\n") else "",
    }
    return rows, info


def _validate(
    rows: list[dict[str, str]], block: dict[str, str], violations: list[str]
) -> None:
    if not rows:
        violations.append("UPDATE_LOG 没有数据行，无法与 README 标记块比对")
        return
    if len(rows) > MAX_ROWS:
        violations.append(f"UPDATE_LOG 数据行 {len(rows)} 超过上限 {MAX_ROWS}")
    for index, row in enumerate(rows, start=1):
        if row["#"] != str(index):
            violations.append(
                f"UPDATE_LOG 第 {index} 行编号应为 {index}，实际 {row['#']!r}"
            )
        if not DATE_RE.match(row["日期"]):
            violations.append(f"UPDATE_LOG 第 {index} 行日期格式错误：{row['日期']!r}")
        try:
            date.fromisoformat(row["日期"])
        except ValueError:
            violations.append(
                f"UPDATE_LOG 第 {index} 行日期不是真实日期：{row['日期']!r}"
            )
        for field in FIELDS:
            if not row[field]:
                violations.append(f"UPDATE_LOG 第 {index} 行字段「{field}」为空")
    dates = [row["日期"] for row in rows if DATE_RE.match(row["日期"])]
    # 最新在第 1 行：逐行应满足 date[i] >= date[i+1]（非递增）。
    # 违反条件是「后一行比前一行更新」，即 later > earlier。
    if any(later > earlier for earlier, later in zip(dates, dates[1:])):
        violations.append("UPDATE_LOG 日期必须非递增（最新在第 1 行）")
    pairs = [(row["日期"], row["更新内容"]) for row in rows]
    if len(set(pairs)) != len(pairs):
        violations.append("UPDATE_LOG 存在重复的 (日期, 更新内容) 组合")
    for field in FIELDS:
        if block[field] != rows[0][field]:
            violations.append(
                f"README 标记块「{field}」与台账第 1 行不一致："
                f"{block[field]!r} != {rows[0][field]!r}"
            )


def check(readme_path: Path = README, log_path: Path = UPDATE_LOG) -> int:
    violations: list[str] = []
    if not readme_path.is_file():
        violations.append(f"缺少 README：{readme_path}")
    if not log_path.is_file():
        violations.append(f"缺少更新台账：{log_path}")
    if violations:
        for item in violations:
            print(f"  [error] {item}", file=sys.stderr)
        print("record_update: check=error（文件缺失，绝不静默跳过）", file=sys.stderr)
        return 1

    readme_text = readme_path.read_text(encoding="utf-8")
    log_text = log_path.read_text(encoding="utf-8")
    block = _parse_block(readme_text, violations)
    parsed = _parse_table(log_text, violations)
    if block is not None and parsed is not None:
        _validate(parsed[0], block, violations)
    if violations:
        for item in violations:
            print(f"  [error] {item}", file=sys.stderr)
        print("record_update: ok=False", file=sys.stderr)
        return 1
    rows = parsed[0] if parsed else []
    print(f"record_update: entries={len(rows)} ok=True")
    return 0


def add(
    *,
    day: str,
    ref: str,
    summary: str,
    evidence: str,
    readme_path: Path = README,
    log_path: Path = UPDATE_LOG,
) -> int:
    values = {"日期": day, "版本/ref": ref, "更新内容": summary, "证据": evidence}
    if not DATE_RE.match(day):
        print("record_update: --date 必须是 YYYY-MM-DD", file=sys.stderr)
        return 1
    try:
        date.fromisoformat(day)
    except ValueError:
        print(f"record_update: --date 不是真实日期：{day}", file=sys.stderr)
        return 1
    for field, value in values.items():
        if not value.strip():
            print(f"record_update: 字段「{field}」不能为空", file=sys.stderr)
            return 1
        if "|" in value or "\n" in value or "\r" in value:
            print(f"record_update: 字段「{field}」不能含 | 或换行", file=sys.stderr)
            return 1
    if not readme_path.is_file() or not log_path.is_file():
        print(
            "record_update: README.md / docs/UPDATE_LOG.md 必须已存在", file=sys.stderr
        )
        return 1

    violations: list[str] = []
    readme_text = readme_path.read_text(encoding="utf-8")
    log_text = log_path.read_text(encoding="utf-8")
    if _parse_block(readme_text, violations) is None:
        for item in violations:
            print(f"  [error] {item}", file=sys.stderr)
        print("record_update: README 标记块不可用，拒绝写入", file=sys.stderr)
        return 1
    parsed = _parse_table(log_text, violations)
    if parsed is None:
        for item in violations:
            print(f"  [error] {item}", file=sys.stderr)
        print("record_update: UPDATE_LOG 表格不可用，拒绝写入", file=sys.stderr)
        return 1
    rows, info = parsed

    merged = [{"#": "0", **values}] + [
        {**row, "#": "0"} for row in rows[: MAX_ROWS - 1]
    ]
    merged = merged[:MAX_ROWS]
    for index, row in enumerate(merged, start=1):
        row["#"] = str(index)

    lines: list[str] = list(info["lines"])  # type: ignore[arg-type]
    first = int(info["first_data"])
    end = int(info["data_end"])
    new_lines = lines[:first] + [_row_line(row) for row in merged] + lines[end:]
    log_text = "\n".join(new_lines) + str(info["trailing"])

    start = readme_text.index(BEGIN) + len(BEGIN)
    stop = readme_text.index(END, start)
    readme_text = readme_text[:start] + _block_text(values) + readme_text[stop:]

    readme_path.write_text(readme_text, encoding="utf-8", newline="\n")
    log_path.write_text(log_text, encoding="utf-8", newline="\n")
    print(f"record_update: add=ok entries={len(merged)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="README 更新块 / 台账一致性工具")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="只读一致性校验（CI 用）")
    group.add_argument("--add", action="store_true", help="插入一条最新更新")
    ap.add_argument("--date", default="", help="--add：YYYY-MM-DD")
    ap.add_argument("--ref", default="", help="--add：版本/ref")
    ap.add_argument("--summary", default="", help="--add：更新内容")
    ap.add_argument("--evidence", default="", help="--add：证据路径")
    args = ap.parse_args(argv)

    if args.check:
        return check()
    if not all((args.date, args.ref, args.summary, args.evidence)):
        print(
            "record_update: --add 需要 --date/--ref/--summary/--evidence",
            file=sys.stderr,
        )
        return 1
    return add(
        day=args.date,
        ref=args.ref,
        summary=args.summary,
        evidence=args.evidence,
    )


if __name__ == "__main__":
    raise SystemExit(main())
