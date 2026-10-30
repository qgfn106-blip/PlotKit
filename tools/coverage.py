"""生成覆盖率表：registry 里每个 kind 的维度 / 绘制器 / 数据键 / 预设。

    PYTHONPATH=src python tools/coverage.py            # markdown 表格
    PYTHONPATH=src python tools/coverage.py --check    # 有缺项就非零退出（CI 用）
"""

from __future__ import annotations

import argparse
import sys

from plotkit.backends import registry as reg
from plotkit.backends.mpl_backend import DRAWERS
from plotkit.presets import KIND_PRESETS
from plotkit.spec.validate import REQUIRED_DATA

#: §3.4 方法表里点名要覆盖的 18 种（MultiPlotter 口径）
MATRIX_18 = [
    # 11 个 2D：line / scatter(marker) / bar / hist / pie / image / table
    #           + heatmap / contour / quiver / streamplot
    #（correlation 是 MultiPlotter 之外的聚合 kind，不计入 18）
    "line", "marker", "bar", "hist", "pie", "image", "table",
    "heatmap", "contour", "quiver", "streamplot",
    # 7 个 3D
    "surface", "line3d", "scatter3d", "bar3d", "hist3d", "quiver3d", "stream3d",
]


def rows() -> list[tuple[str, int, str, str, str, str]]:
    out = []
    for kind in sorted(reg.kinds()):
        spec = reg.resolve(kind)
        out.append((
            kind,
            spec.dimension,
            "✅" if kind in DRAWERS else "—",
            ", ".join(REQUIRED_DATA.get(kind, {})) or "—",
            "✅" if kind in KIND_PRESETS else "—",
            spec.description or "",
        ))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="有缺项时返回非零")
    args = parser.parse_args()

    data = rows()
    print("| kind | 维 | mpl 绘制器 | 数据键 | 预设 | 说明 |")
    print("| --- | --- | --- | --- | --- | --- |")
    for row in data:
        print("| " + " | ".join(str(v) for v in row) + " |")

    covered = {k for k, *_ in data}
    missing = [k for k in MATRIX_18 if k not in covered]
    no_drawer = [k for k, _, drawer, *_ in data if drawer != "✅"]
    print()
    print(f"- registry 共 **{len(data)}** 种；18 种矩阵覆盖 **{len(MATRIX_18) - len(missing)}/18**")
    print(f"- 缺绘制器：{', '.join(no_drawer) or '无'}")
    print(f"- 18 种矩阵缺口：{', '.join(missing) or '无'}")
    if args.check and (missing or no_drawer):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
