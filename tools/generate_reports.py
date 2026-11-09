#!/usr/bin/env python3
"""按顺序运行三个 P0 契约闸门，重生成 reports/*.json，并打印一行汇总。"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
for entry in (str(HERE), str(ROOT / "src")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import check_capability_matrix  # noqa: E402
import check_doc_sync  # noqa: E402
import check_layers  # noqa: E402

CHECKERS = (
    ("layers", check_layers),
    ("capability_matrix", check_capability_matrix),
    ("doc_sync", check_doc_sync),
)

# 裁定 ⑨-4：理想环境重放必须显式钉定 available，绝不吃运行时 probe 采样。
# 与 `python tools/check_capability_matrix.py` 独立运行写出完全相同的字节。
ALL_EXTRAS = {"three": True, "ns": True}


def main(argv: list[str] | None = None) -> int:
    codes = []
    for name, module in CHECKERS:
        if name == "capability_matrix":
            code = module.run(write=True, quiet=True, available=ALL_EXTRAS)
        else:
            code = module.run(write=True, quiet=True)
        codes.append(code)
    summary = "; ".join(
        f"{name}={'ok' if code == 0 else 'FAIL'}"
        for (name, _), code in zip(CHECKERS, codes)
    )
    print(f"generate_reports: {summary}")
    return 1 if any(codes) else 0


if __name__ == "__main__":
    sys.exit(main())
