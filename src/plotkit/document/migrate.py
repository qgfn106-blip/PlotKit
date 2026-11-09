"""0.1 spec ↔ v1 FigureDocument 的纯函数迁移（L1，仅依赖 L0 schema）。

约定：
- ``legacy`` 原样保存整份 0.1 输入，``to_v0`` 优先走它，保证黄金往返；
- 未知顶层 / figure / layer 字段分别进入 ``extensions`` 的三个袋子；
- 所有输出用普通 JSON 容器，函数永不修改入参。
"""

from __future__ import annotations

import copy
import importlib
import json
import math
import sys
from typing import TYPE_CHECKING, Any

from plotkit.schema import load

if TYPE_CHECKING:
    # 仅给类型检查器/静态分析器一个名字；运行时绝不导入同层 model。
    FigureDocument = Any

FIGURE_SCHEMA = "plotkit.figure/v1"

# 由 document/__init__.py 注入；避免 migrate.py 静态 import model 造成环。
_REPORT_TYPE: Any | None = None

_KNOWN_TOP_KEYS = {"spec_version", "figure", "layers"}
_KNOWN_FIGURE_KEYS = {
    "size",
    "dpi",
    "ncols",
    "subplots",
    "theme",
    "title",
    "link_x",
    "window",
    "fonts",
    "shapes",
    "insets",
    "anim",
    "layout",
    "notes",
    "background",
    "margin",
}
_KNOWN_LAYER_KEYS = {
    "id",
    "kind",
    "subplot",
    "data",
    "label",
    "legend",
    "style",
    "view",
    "annotations",
    "rect",
    "link_to",
    "locked",
    "z_order",
    "axes",
    "plots",
}
_FORWARD_FIGURE_KEYS = (
    "fonts",
    "window",
    "link_x",
    "ncols",
    "subplots",
    "insets",
    "shapes",
    "notes",
    "layout",
    "anim",
)


def _report(errors: Any = (), warnings: Any = ()) -> Any:
    cls = _REPORT_TYPE
    if cls is None:
        module = sys.modules.get("plotkit.document.model")
        if module is None:
            module = importlib.import_module("plotkit.document.model")
        cls = module.Report
    return cls(errors=tuple(errors), warnings=tuple(warnings))


def _deep(value: Any) -> Any:
    return copy.deepcopy(value)


def _json_default(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return value.to_dict()
    return repr(value)


def _plain(value: Any) -> Any:
    """深拷贝并还原冻结代理为普通 JSON 容器。"""
    return json.loads(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            default=_json_default,
        )
    )


def canonical_json(value: Any) -> str:
    """确定性 JSON 文本，供哈希/比较辅助使用。"""
    return json.dumps(
        _plain(value),
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _num(value: Any, default: float = 0.0) -> float:
    return float(value) if _is_number(value) else float(default)


def _int(value: Any, default: int = 1) -> int:
    if isinstance(value, bool):
        return int(default)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return int(default)


def _num_list(value: Any, size: int, default: list[float]) -> list[float]:
    if isinstance(value, (list, tuple)) and len(value) == size:
        if all(_is_number(item) for item in value):
            return [float(item) for item in value]
    return list(default)


def _pair(value: Any) -> list[float] | None:
    if isinstance(value, (list, tuple)) and len(value) == 2:
        if all(_is_number(item) for item in value):
            return [float(item) for item in value]
    return None


def _ticks(value: Any) -> list[float]:
    if isinstance(value, (list, tuple)):
        return [float(item) for item in value if _is_number(item)]
    return []


def _sorted_dict(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}
    return {str(key): _deep(value[key]) for key in sorted(value, key=str)}


def _grid_rect(slot: Any, ncols: Any, subplots: Any) -> list[float]:
    """等宽网格，y 从顶部往下排；slot 按行优先展开。"""
    cols = max(1, _int(ncols, 1))
    total = max(1, _int(subplots, 1))
    rows = max(1, math.ceil(total / cols))
    index = max(0, _int(slot, 0))
    col = index % cols
    row = index // cols
    width = 1.0 / cols
    height = 1.0 / rows
    x = col * width
    y = 1.0 - (row + 1) * height
    return [round(x, 12), round(y, 12), round(width, 12), round(height, 12)]


def _axes_from_view(view: Any) -> dict:
    raw = view if isinstance(view, dict) else {}
    return {
        "xlabel": raw.get("xlabel"),
        "ylabel": raw.get("ylabel"),
        "xlim": _pair(raw.get("xlim")),
        "ylim": _pair(raw.get("ylim")),
        "xscale": str(raw.get("xscale", "linear")),
        "yscale": str(raw.get("yscale", "linear")),
        "grid": bool(raw.get("grid", True)),
        "invert_y": bool(raw.get("invert_y", False)),
        "zero_line": bool(raw.get("zero_line", False)),
        "ticks": _ticks(raw.get("ticks")),
        "loglabels": str(raw.get("loglabels", "sci")),
    }


def _plot_from_layer(layer: dict, index: int) -> dict:
    data = layer.get("data") if isinstance(layer.get("data"), dict) else {}
    return {
        "id": str(layer.get("id") or f"P{index}"),
        "kind": str(layer.get("kind") or "line"),
        "x": data.get("x"),
        "y": data.get("y"),
        "label": layer.get("label"),
        "legend": bool(layer.get("legend", True)),
        "style": _sorted_dict(layer.get("style")),
        "view": _sorted_dict(layer.get("view")),
    }


def _note_from_raw(note: Any, index: int) -> dict:
    raw = note if isinstance(note, dict) else {}
    pos = _num_list(raw.get("pos"), 2, [0.0, 0.0])
    return {
        "id": str(raw.get("id") or f"N{index}"),
        "kind": str(raw.get("kind") or "text"),
        "text": str(raw.get("text") or ""),
        "color": str(raw.get("color") or "#333333"),
        "size": _num(raw.get("size"), 12.0),
        "pos": pos,
    }


def _shape_from_raw(shape: Any, index: int) -> dict:
    raw = shape if isinstance(shape, dict) else {}
    rect = _num_list(raw.get("rect"), 4, [0.0, 0.0, 1.0, 1.0])
    kind = raw.get("type") or raw.get("kind") or "rect"
    return {
        "id": str(raw.get("id") or f"S{index}"),
        "kind": str(kind),
        "rect": rect,
    }


def _data_names(layers: list[Any]) -> list[str]:
    names: set[str] = set()
    for layer in layers:
        if not isinstance(layer, dict):
            continue
        data = layer.get("data")
        if not isinstance(data, dict):
            continue
        for value in data.values():
            if value is not None:
                names.add(str(value))
    return sorted(names)


def _layer_rect(layer: dict, index: int, figure: dict) -> list[float]:
    explicit = layer.get("rect")
    if isinstance(explicit, (list, tuple)) and len(explicit) == 4:
        if all(_is_number(item) for item in explicit):
            return [float(item) for item in explicit]
    slot = layer.get("subplot", index)
    return _grid_rect(
        slot,
        figure.get("ncols", 1),
        figure.get("subplots", len([1])),
    )


def _extensions(raw: dict, figure: dict, layers: list[Any]) -> dict:
    known_figure = {
        key: _deep(value) for key, value in figure.items() if key in _KNOWN_FIGURE_KEYS
    }
    unknown_figure = {
        key: _deep(value)
        for key, value in figure.items()
        if key not in _KNOWN_FIGURE_KEYS
    }
    unknown_top = {
        key: _deep(value) for key, value in raw.items() if key not in _KNOWN_TOP_KEYS
    }
    unknown_layers: list[dict] = []
    for index, layer in enumerate(layers):
        if not isinstance(layer, dict):
            continue
        fields = {
            key: _deep(value)
            for key, value in layer.items()
            if key not in _KNOWN_LAYER_KEYS
        }
        if fields:
            unknown_layers.append({"index": index, "fields": fields})
    ext: dict[str, Any] = {
        "spec_version": raw.get("spec_version", "0.1"),
        "figure": known_figure,
        "layers": _deep(layers),
        "unknown_top": unknown_top,
        "unknown_figure": unknown_figure,
        "unknown_layers": unknown_layers,
    }
    for key in _FORWARD_FIGURE_KEYS:
        if key in figure:
            ext[key] = _deep(figure[key])
    # 未知字段同时保留一份平铺别名，便于宿主按原键名检索。
    for bag in (unknown_top, unknown_figure):
        for key, value in bag.items():
            ext.setdefault(key, _deep(value))
    for entry in unknown_layers:
        fields = entry.get("fields", {})
        if isinstance(fields, dict):
            for key, value in fields.items():
                ext.setdefault(key, _deep(value))
    return ext


def migrate_v0_to_v1(raw: dict) -> dict:
    """把 0.1 spec 显式迁移为 v1 dict；不修改入参。"""
    if not isinstance(raw, dict):
        raise ValueError("migrate_v0_to_v1 需要 0.1 spec dict")
    original = _deep(raw)
    figure = raw.get("figure") if isinstance(raw.get("figure"), dict) else {}
    raw_layers = raw.get("layers") if isinstance(raw.get("layers"), list) else []
    layers = [item for item in raw_layers if isinstance(item, dict)]
    link_x = bool(figure.get("link_x", False))
    link_to = 0 if link_x else None

    v1_layers: list[dict] = []
    for index, layer in enumerate(layers):
        v1_layers.append(
            {
                "id": str(layer.get("id") or f"L{index}"),
                "rect": _layer_rect(layer, index, figure),
                "axes": _axes_from_view(layer.get("view")),
                "plots": [_plot_from_layer(layer, index)],
                "link_to": link_to,
                "locked": False,
                "z_order": index,
            }
        )

    notes_raw = figure.get("notes", raw.get("notes", []))
    shapes_raw = figure.get("shapes", raw.get("shapes", []))
    notes = [
        _note_from_raw(item, index)
        for index, item in enumerate(notes_raw)
        if isinstance(notes_raw, (list, tuple))
    ]
    shapes = [
        _shape_from_raw(item, index)
        for index, item in enumerate(shapes_raw)
        if isinstance(shapes_raw, (list, tuple))
    ]

    return {
        "schema": FIGURE_SCHEMA,
        "revision": 0,
        "page": {
            "size": _num_list(figure.get("size"), 2, [12.8, 8.4]),
            "dpi": _int(figure.get("dpi"), 100),
            "margin": [0.0, 0.0, 0.0, 0.0],
            "background": "white",
            "title": figure.get("title"),
        },
        "layers": v1_layers,
        "theme": {
            "name": str(figure.get("theme", "default")),
            "revision": 0,
        },
        "notes": notes,
        "shapes": shapes,
        "data": {
            "names": _data_names(layers),
            "store": "default",
            "version": 0,
        },
        "legacy": original,
        "extensions": _extensions(raw, figure, layers),
    }


def _v0_layer(v1_layer: dict, index: int) -> dict:
    plots = v1_layer.get("plots") if isinstance(v1_layer.get("plots"), list) else []
    plot = plots[0] if plots and isinstance(plots[0], dict) else {}
    data: dict[str, Any] = {}
    if plot.get("x") is not None:
        data["x"] = plot["x"]
    if plot.get("y") is not None:
        data["y"] = plot["y"]
    return {
        "id": v1_layer.get("id", f"L{index}"),
        "kind": plot.get("kind", "line"),
        "subplot": index,
        "data": data,
        "label": plot.get("label"),
        "legend": plot.get("legend", True),
        "style": _plain(plot.get("style", {})),
        "view": _plain(plot.get("view", {})),
        "annotations": [],
        "rect": _plain(v1_layer.get("rect", [0.0, 0.0, 1.0, 1.0])),
    }


def _v0_note(note: dict) -> dict:
    return _plain(note)


def _v0_shape(shape: dict) -> dict:
    raw = _plain(shape)
    raw["type"] = raw.pop("kind", "rect")
    return raw


def _reconstruct_v0(raw: dict) -> dict:
    page = raw.get("page") if isinstance(raw.get("page"), dict) else {}
    theme = raw.get("theme") if isinstance(raw.get("theme"), dict) else {}
    v1_layers = raw.get("layers") if isinstance(raw.get("layers"), list) else []
    ext = _plain(raw.get("extensions") or {})
    figure_ext = ext.get("figure") if isinstance(ext.get("figure"), dict) else {}
    unknown_figure = (
        ext.get("unknown_figure") if isinstance(ext.get("unknown_figure"), dict) else {}
    )
    unknown_top = (
        ext.get("unknown_top") if isinstance(ext.get("unknown_top"), dict) else {}
    )
    original_layers = ext.get("layers") if isinstance(ext.get("layers"), list) else []
    unknown_layers = (
        ext.get("unknown_layers") if isinstance(ext.get("unknown_layers"), list) else []
    )
    link_x = any(
        isinstance(layer, dict) and layer.get("link_to") is not None
        for layer in v1_layers
    )
    figure: dict[str, Any] = {
        "size": _plain(page.get("size", [12.8, 8.4])),
        "dpi": page.get("dpi", 100),
        "ncols": ext.get("ncols", figure_ext.get("ncols", 1)),
        "subplots": ext.get("subplots", figure_ext.get("subplots", len(v1_layers))),
        "theme": theme.get("name", "default"),
        "title": page.get("title"),
        "link_x": link_x,
        "window": ext.get("window", figure_ext.get("window")),
        "fonts": _plain(ext.get("fonts", figure_ext.get("fonts", {}))),
        "shapes": _plain(ext.get("shapes", figure_ext.get("shapes", []))),
        "insets": _plain(ext.get("insets", figure_ext.get("insets", []))),
    }
    for key, value in figure_ext.items():
        if key not in figure:
            figure[key] = _plain(value)
    if "notes" not in figure:
        notes = raw.get("notes") if isinstance(raw.get("notes"), list) else []
        figure["notes"] = [_v0_note(item) for item in notes if isinstance(item, dict)]
    if "shapes" not in figure:
        shapes = raw.get("shapes") if isinstance(raw.get("shapes"), list) else []
        figure["shapes"] = [
            _v0_shape(item) for item in shapes if isinstance(item, dict)
        ]
    for key, value in unknown_figure.items():
        figure[key] = _plain(value)

    layers: list[dict] = []
    for index, v1_layer in enumerate(v1_layers):
        if not isinstance(v1_layer, dict):
            continue
        original = original_layers[index] if index < len(original_layers) else None
        layer = (
            _plain(original)
            if isinstance(original, dict)
            else _v0_layer(v1_layer, index)
        )
        for entry in unknown_layers:
            if not isinstance(entry, dict) or entry.get("index") != index:
                continue
            fields = entry.get("fields")
            if isinstance(fields, dict):
                for key, value in fields.items():
                    layer[key] = _plain(value)
        layers.append(layer)

    result: dict[str, Any] = {
        "spec_version": ext.get("spec_version", "0.1"),
        "figure": figure,
        "layers": layers,
    }
    for key, value in unknown_top.items():
        result[key] = _plain(value)
    return result


def to_v0(doc: dict | FigureDocument) -> dict:
    """反向迁移；legacy 存在时逐字节等价返回，否则按 v1 重建 0.1。"""
    if hasattr(doc, "to_dict") and callable(doc.to_dict):
        raw = doc.to_dict()
    elif isinstance(doc, dict):
        raw = doc
    else:
        raise ValueError("to_v0 需要 dict 或 FigureDocument")
    if not isinstance(raw, dict):
        raise ValueError("to_v0 展开后必须是 dict")
    legacy = raw.get("legacy")
    if legacy is not None:
        return _plain(legacy)
    return _reconstruct_v0(raw)


def validate_document(raw: dict) -> Any:
    """独立严格校验 v1 dict；返回 Report，任何输入都不抛异常。"""
    if not isinstance(raw, dict):
        return _report(errors=("validate_document 需要 dict",))
    try:
        schema = load("figure.v1.json")
        allowed = set(schema["properties"])
        required = set(schema["required"])
    except Exception as exc:  # 契约文件损坏也要以 Report 形式暴露
        return _report(errors=(f"无法读取 figure.v1.json：{exc}",))
    errors: list[str] = []
    unknown = sorted(str(key) for key in raw if key not in allowed)
    if unknown:
        errors.append(f"未知顶层字段：{', '.join(unknown)}")
    missing = sorted(required - set(raw))
    if missing:
        errors.append(f"缺少必填字段：{', '.join(missing)}")
    if raw.get("schema") != FIGURE_SCHEMA:
        errors.append(f"schema 必须为 {FIGURE_SCHEMA!r}")
    revision = raw.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        errors.append("revision 必须是 >=0 的整数")
    for key, expected in (
        ("page", dict),
        ("layers", list),
        ("theme", dict),
        ("data", dict),
    ):
        if not isinstance(raw.get(key), expected):
            errors.append(f"{key} 必须是 {expected.__name__}")
    for key in ("notes", "shapes"):
        if key in raw and not isinstance(raw[key], list):
            errors.append(f"{key} 必须是数组")
    if (
        "template" in raw
        and raw["template"] is not None
        and not isinstance(raw["template"], dict)
    ):
        errors.append("template 必须是对象或 null")
    for key in ("legacy", "extensions"):
        if key in raw and raw[key] is not None and not isinstance(raw[key], dict):
            errors.append(f"{key} 必须是对象或 null")
    return _report(errors=tuple(errors))


__all__ = [
    "FIGURE_SCHEMA",
    "migrate_v0_to_v1",
    "to_v0",
    "validate_document",
    "canonical_json",
]
