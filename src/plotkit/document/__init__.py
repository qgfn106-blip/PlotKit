"""FigureDocument v1 的公共入口（L1 装配层）。

职责：把 ``model`` 的冻结数据类与 ``migrate`` 的纯函数装配起来，
并注入两边的回调，避免 L1 内部出现静态环依赖。
"""

from __future__ import annotations

from . import migrate as _migrate
from . import model as _model
from .migrate import (
    canonical_json,
    migrate_v0_to_v1,
    to_v0,
    validate_document,
)
from .model import (
    FIGURE_SCHEMA,
    AxesSpec,
    ColumnRefs,
    FigureDocument,
    LayerSpec,
    NoteSpec,
    PageSpec,
    PlotSpec,
    Report,
    ShapeSpec,
    TemplateRef,
    ThemeRef,
)

# model.py 的三个包装器通过此表回调 migrate.py；migrate.py 的 Report
# 也在这里获得，避免任一模块静态导入对方。
_model._DELEGATES.update(
    {
        "migrate": migrate_v0_to_v1,
        "to_v0": to_v0,
        "validate": validate_document,
    }
)
_migrate._REPORT_TYPE = Report

__all__ = [
    "FIGURE_SCHEMA",
    "Report",
    "PageSpec",
    "AxesSpec",
    "ThemeRef",
    "TemplateRef",
    "NoteSpec",
    "ShapeSpec",
    "PlotSpec",
    "LayerSpec",
    "ColumnRefs",
    "FigureDocument",
    "migrate_v0_to_v1",
    "to_v0",
    "validate_document",
    "canonical_json",
]
