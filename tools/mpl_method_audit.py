"""PK-R12 对账：matplotlib `Axes` 绘图方法 → 归属（独立 kind / 复用 kind / shapes / 轴级 / 不做）。

用法：
    PYTHONPATH=src python tools/mpl_method_audit.py            # 打印归属表
    PYTHONPATH=src python tools/mpl_method_audit.py --check    # 有任何未归属/悬空引用则非零退出

口径（docs/REQUIREMENTS_AND_PROGRESS.md §3.4）：
    双后端 / mpl 兜底 / 不做 —— D33 之后统一走 matplotlib，归属改为「要不要 figure 级字段」：
      kind        独立建 kind（渲染由 mpl_backend.DRAWERS 或注册 builder 提供）
      reuse       复用某个已注册 kind（附 note 说明如何表达）
      shapes      由 figure.shapes 表达
      annotations 由 layer.annotations 表达
      axis        轴级字段（view.* / figure.axes），不建 kind
      skip        明确不做（note 必须写原因）
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

import plotkit  # noqa: F401  (导入即触发 registry 的 kind 注册)

FORM_KIND = "kind"
FORM_REUSE = "reuse"
FORM_SHAPES = "shapes"
FORM_ANNOTATIONS = "annotations"
FORM_AXIS = "axis"
FORM_SKIP = "skip"
_FORMS = {FORM_KIND, FORM_REUSE, FORM_SHAPES, FORM_ANNOTATIONS, FORM_AXIS, FORM_SKIP}


@dataclass(frozen=True)
class Method:
    name: str
    form: str
    target: str = ""
    note: str = ""


#: matplotlib `Axes` / `Axes3D` 的绘图方法全集（约 55–70 个，含常用别名）。
MPL_METHODS: list[Method] = [
    # ---- 线 / 点 / 柱 / 面积 ----
    Method("plot", FORM_KIND, "line"),
    Method("scatter", FORM_KIND, "marker"),
    Method("bar", FORM_KIND, "bar"),
    Method("barh", FORM_KIND, "barh"),
    Method("bar_label", FORM_REUSE, "bar", "柱顶数值标注走 annotations.text"),
    Method("errorbar", FORM_REUSE, "line", "误差棒用 line 的 error_x/error_y"),
    Method(
        "fill_between",
        FORM_REUSE,
        "stackplot",
        "面积填充用 stackplot，或 figure.shapes",
    ),
    Method("fill_betweenx", FORM_REUSE, "stackplot", "同上（横向）"),
    Method("fill", FORM_SHAPES, note="任意多边形装饰用 figure.shapes.path"),
    Method("stackplot", FORM_KIND, "stackplot"),
    Method("stem", FORM_KIND, "stem"),
    Method("step", FORM_KIND, "step"),
    Method("stairs", FORM_KIND, "stairs"),
    Method("broken_barh", FORM_KIND, "broken_barh"),
    Method("eventplot", FORM_KIND, "eventplot"),
    Method("vlines", FORM_SHAPES, note="竖线走 figure.shapes.line"),
    Method("hlines", FORM_SHAPES, note="横线走 figure.shapes.line"),
    Method("axhline", FORM_ANNOTATIONS, note="layer.annotations 的 hline"),
    Method("axvline", FORM_ANNOTATIONS, note="layer.annotations 的 vline"),
    Method("axline", FORM_SHAPES, note="斜线走 figure.shapes.line"),
    Method("axhspan", FORM_ANNOTATIONS, note="layer.annotations 的 band"),
    Method("axvspan", FORM_SHAPES, note="竖带用 figure.shapes.rect"),
    Method("loglog", FORM_AXIS, note="view.xscale=yscale=log"),
    Method("semilogx", FORM_AXIS, note="view.xscale=log"),
    Method("semilogy", FORM_AXIS, note="view.yscale=log"),
    # ---- 统计 ----
    Method("hist", FORM_KIND, "hist"),
    Method("hist2d", FORM_REUSE, "heatmap", "二维直方用 heatmap 表达"),
    Method("boxplot", FORM_KIND, "boxplot"),
    Method("violinplot", FORM_KIND, "violinplot"),
    Method("bxp", FORM_KIND, "bxp"),
    Method("pie", FORM_KIND, "pie"),
    Method("ecdf", FORM_KIND, "ecdf"),
    Method("hexbin", FORM_KIND, "hexbin"),
    # ---- 图像 / 场 ----
    Method("imshow", FORM_KIND, "image"),
    Method("matshow", FORM_REUSE, "heatmap", "matshow = 带矩阵刻度的 imshow"),
    Method("pcolor", FORM_REUSE, "heatmap"),
    Method("pcolormesh", FORM_REUSE, "heatmap"),
    Method("pcolorfast", FORM_REUSE, "heatmap"),
    Method("spy", FORM_SKIP, note="稀疏矩阵可视化，用 heatmap/image 表达，不单建 kind"),
    Method(
        "figimage",
        FORM_SKIP,
        note="绕过 artist 直接贴像素图，与 image kind 语义重合，不做",
    ),
    Method("contour", FORM_KIND, "contour"),
    Method("contourf", FORM_KIND, "contourf"),
    Method("clabel", FORM_REUSE, "contour", "contour 的 labels=True"),
    # ---- 矢量 ----
    Method("quiver", FORM_KIND, "quiver"),
    Method("quiverkey", FORM_REUSE, "quiver", "quiver 的 key=True"),
    Method("streamplot", FORM_KIND, "streamplot"),
    Method("barbs", FORM_KIND, "barbs"),
    # ---- 三角 / 非结构 ----
    Method("triplot", FORM_KIND, "triplot"),
    Method("tricontour", FORM_KIND, "tricontour"),
    Method("tricontourf", FORM_KIND, "tricontourf"),
    Method("tripcolor", FORM_KIND, "tripcolor"),
    # ---- 信号 ----
    Method("psd", FORM_KIND, "psd"),
    Method("csd", FORM_KIND, "csd"),
    Method("specgram", FORM_KIND, "specgram"),
    Method("cohere", FORM_KIND, "cohere"),
    Method("acorr", FORM_KIND, "acorr"),
    Method("xcorr", FORM_KIND, "xcorr"),
    Method("angle_spectrum", FORM_KIND, "angle_spectrum"),
    Method("magnitude_spectrum", FORM_KIND, "magnitude_spectrum"),
    Method("phase_spectrum", FORM_KIND, "phase_spectrum"),
    # ---- 3D ----
    Method("plot3D", FORM_KIND, "line3d"),
    Method("scatter3D", FORM_KIND, "scatter3d"),
    Method("bar3d", FORM_KIND, "bar3d"),
    Method("plot_surface", FORM_KIND, "surface"),
    Method("plot_wireframe", FORM_REUSE, "surface", "surface 的 wireframe 参数"),
    Method("contour3D", FORM_REUSE, "surface", "surface 的 contour 参数"),
    Method("contourf3D", FORM_REUSE, "surface", "surface 的 contourf 参数"),
    Method("quiver3D", FORM_KIND, "quiver3d"),
    Method("voxels", FORM_KIND, "voxels"),
    Method("trisurf", FORM_KIND, "trisurf"),
    Method("stem3D", FORM_KIND, "stem3d"),
    Method("text3D", FORM_KIND, "text3d"),
    # ---- 轴级 / 装饰 ----
    Method("twinx", FORM_AXIS, note="双 y 轴，走 figure.axes 字段（D28）"),
    Method("twiny", FORM_AXIS, note="双 x 轴，走 figure.axes 字段"),
    Method("secondary_xaxis", FORM_AXIS, note="次坐标轴走 figure.axes"),
    Method("secondary_yaxis", FORM_AXIS, note="次坐标轴走 figure.axes"),
    Method("colorbar", FORM_AXIS, note="kind 的 colorbar=True 样式"),
    Method("legend", FORM_AXIS, note="layer.legend / figure 级 legend"),
    Method("grid", FORM_AXIS, note="view.grid"),
    Method("table", FORM_KIND, "table"),
    Method("annotate", FORM_ANNOTATIONS, note="layer.annotations.text"),
    Method("arrow", FORM_SHAPES, note="figure.shapes.arrow"),
    Method("text", FORM_ANNOTATIONS, note="layer.annotations.text"),
]


def _kinds() -> set[str]:
    from plotkit.backends import registry as reg

    return set(reg.kinds()) | set(reg.ALIASES)


def audit() -> list[str]:
    """返回问题清单（空 = 对账通过）。"""
    problems: list[str] = []
    seen: dict[str, int] = {}
    kinds_ok = _kinds()
    for i, m in enumerate(MPL_METHODS):
        if m.name in seen:
            problems.append(f"方法重复: {m.name}")
        seen[m.name] = i
        if m.form not in _FORMS:
            problems.append(f"{m.name}: 未知归属形态 {m.form!r}")
            continue
        if m.form in (FORM_KIND, FORM_REUSE):
            if not m.target:
                problems.append(f"{m.name}: {m.form} 未指定目标 kind")
            elif m.target not in kinds_ok:
                problems.append(f"{m.name}: 目标 kind 未注册 {m.target!r}")
        else:
            if not m.note:
                problems.append(f"{m.name}: {m.form} 必须写 note 说明")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="有问题时返回非零")
    args = parser.parse_args()

    groups: dict[str, list[Method]] = {}
    for m in MPL_METHODS:
        groups.setdefault(m.form, []).append(m)

    print(f"# matplotlib 绘图方法归属（共 {len(MPL_METHODS)} 个）")
    for form in (
        FORM_KIND,
        FORM_REUSE,
        FORM_SHAPES,
        FORM_ANNOTATIONS,
        FORM_AXIS,
        FORM_SKIP,
    ):
        items = groups.get(form, [])
        print(f"\n## {form}（{len(items)}）")
        print("| 方法 | 目标 / 说明 |")
        print("| --- | --- |")
        for m in items:
            desc = m.target if m.target else ""
            if m.note:
                desc = f"{desc} — {m.note}" if desc else m.note
            print(f"| {m.name} | {desc or '—'} |")

    problems = audit()
    print()
    if problems:
        print("[FAIL] 对账未通过：")
        for p in problems:
            print("  - " + p)
        return 1 if args.check else 0
    print(f"[OK] 全部 {len(MPL_METHODS)} 个方法均已归属，引用 kind 全部存在。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
