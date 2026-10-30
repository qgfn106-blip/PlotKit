"""图层预设（对应 MultiPlotter 的 KIND_DEFAULTS，D27）。

- 每个 kind 一份默认样式；注册新 kind 时顺带登记预设，避免样式散落在各后端。
- 合并优先级（低 → 高）：`KIND_PRESETS` < `pk.init()` 全局默认 < `add_plot()` 显式参数 < `**kwargs`。
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

#: kind -> {"style": {...}, "view": {...}, "params": {...}}
#: params 是"服务端要算的东西"（如 hist 的 bins），P13-01 起逐 kind 启用。
KIND_PRESETS: dict[str, dict[str, Any]] = {
    "line": {"style": {"mode": "lines", "width": 1.6}, "view": {}},
    "marker": {"style": {"mode": "markers", "marker": {"size": 7}}, "view": {}},
    "scatter": {"style": {"mode": "markers", "marker": {"size": 7}}, "view": {}},
    "bar": {"style": {"mode": "bars", "width": 0.8}, "view": {}},
    "hist": {"style": {"mode": "bars", "bins": 30, "density": False}, "view": {}},
    "pie": {"style": {"mode": "bars", "autopct": "%1.1f%%"}, "view": {"grid": False}},
    "image": {"style": {"mode": "bars", "cmap": "viridis", "colorbar": True,
                        "origin": "upper", "aspect": "auto"}, "view": {"grid": False}},
    "table": {"style": {"mode": "bars", "fontsize": 10}, "view": {"grid": False}},
    "heatmap": {"style": {"mode": "bars", "cmap": "viridis", "colorbar": True}, "view": {"grid": False}},
    "contour": {"style": {"mode": "bars", "levels": 8, "labels": False, "colorbar": False}, "view": {"grid": False}},
    "contourf": {"style": {"mode": "bars", "levels": 8, "colorbar": True}, "view": {"grid": False}},
    "correlation": {"style": {"mode": "bars", "cmap": "RdBu_r", "vmin": -1.0, "vmax": 1.0,
                              "colorbar": True}, "view": {"grid": False}},
    "quiver": {"style": {"cmap": "viridis", "color_by": "magnitude", "arrowsize": 1.0,
                         "shaft": 0.0035, "colorbar": False}, "view": {"grid": False}},
    "barbs": {"style": {"cmap": "viridis", "color_by": "magnitude", "arrowsize": 6.0,
                        "colorbar": False}, "view": {"grid": False}},
    "streamplot": {"style": {"cmap": "viridis", "density": 1.0, "arrowsize": 1.0,
                             "colorbar": False}, "view": {"grid": False}},
}


def preset(kind: str) -> dict[str, Any]:
    """取某个 kind 的预设副本；未登记返回空结构（不报错，交给注册表兜底）。"""
    return copy.deepcopy(KIND_PRESETS.get(kind, {}))


def register_preset(kind: str, *, style: Mapping[str, Any] | None = None,
                    view: Mapping[str, Any] | None = None,
                    params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """登记/覆盖一个 kind 的预设；返回登记后的副本。"""
    entry = KIND_PRESETS.setdefault(kind, {})
    if style:
        entry.setdefault("style", {}).update(dict(style))
    if view:
        entry.setdefault("view", {}).update(dict(view))
    if params:
        entry.setdefault("params", {}).update(dict(params))
    return copy.deepcopy(entry)


def merged(kind: str, *, style: Mapping[str, Any] | None = None,
           view: Mapping[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """预设 + 显式参数合并，返回 (style, view)。"""
    base = preset(kind)
    out_style = dict(base.get("style") or {})
    out_view = dict(base.get("view") or {})
    for key, value in (style or {}).items():
        if key in ("marker", "error") and isinstance(value, Mapping):
            out_style[key] = {**dict(out_style.get(key) or {}), **dict(value)}
        else:
            out_style[key] = value
    out_view.update(dict(view or {}))
    return out_style, out_view
