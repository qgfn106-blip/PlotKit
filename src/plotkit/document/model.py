"""FigureDocument v1：L1 不可变文档模型（仅依赖 L0 schema 契约）。

设计要点：
- 所有数据类都是 frozen；容器用 tuple，任意 0.1 值会被冻结为可哈希代理。
- ``from_dict`` 严格拒绝未知顶层字段，并记住原始键集合，使 ``to_dict``
  能逐字段往返（列表/元组视为等价）。
- ``legacy`` 保留 0.1 信封原样，``extensions`` 保留前向兼容字段。
"""

from __future__ import annotations

import importlib
import math
from dataclasses import dataclass, field, fields, is_dataclass, replace
from typing import Any, Callable, Literal

from plotkit.schema import load

FIGURE_SCHEMA = "plotkit.figure/v1"

# 由 document/__init__.py 注入，避免 model.py 静态 import 同层 migrate 模块。
_DELEGATES: dict[str, Callable[..., Any] | None] = {
    "migrate": None,
    "to_v0": None,
    "validate": None,
}


class _FrozenDict(dict):
    """可哈希的只读 dict 代理；to_dict 时再解冻为普通 dict。"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        object.__setattr__(self, "_hash_cache", None)

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("冻结文档中的映射不可修改")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable

    def __hash__(self) -> int:  # type: ignore[override]
        cached = object.__getattribute__(self, "_hash_cache")
        if cached is None:
            items = tuple(sorted((k, _freeze(v)) for k, v in self.items()))
            cached = hash(items)
            object.__setattr__(self, "_hash_cache", cached)
        return cached

    def __copy__(self) -> "_FrozenDict":
        return self

    def __deepcopy__(self, memo: dict[int, Any]) -> "_FrozenDict":
        return self


class _FrozenList(tuple):
    """可哈希的只读序列代理；to_dict 时再解冻为普通 list。"""

    def __new__(cls, values: Any = ()) -> "_FrozenList":
        return super().__new__(cls, values)

    def __deepcopy__(self, memo: dict[int, Any]) -> "_FrozenList":
        return self


def _freeze(value: Any) -> Any:
    """把任意 JSON 值递归冻结为可哈希对象（dict/list 分别转代理）。"""
    if isinstance(value, (_FrozenDict, _FrozenList)):
        return value
    if isinstance(value, dict):
        ordered = sorted(value.items(), key=lambda item: str(item[0]))
        return _FrozenDict((key, _freeze(item)) for key, item in ordered)
    if isinstance(value, (list, tuple, set, frozenset)):
        items = list(value)
        if isinstance(value, (set, frozenset)):
            items = sorted(items, key=repr)
        return _FrozenList(_freeze(item) for item in items)
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


def _thaw(value: Any) -> Any:
    """把冻结代理递归还原为普通 JSON 容器；保持值不变。"""
    if is_dataclass(value) and not isinstance(value, type):
        return _dump_dataclass(value)
    if isinstance(value, _FrozenDict):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, _FrozenList):
        return [_thaw(item) for item in value]
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, list):
        return [_thaw(item) for item in value]
    if isinstance(value, dict):
        return {key: _thaw(item) for key, item in value.items()}
    return value


def _set_present(obj: Any, raw: dict) -> None:
    """记录 from_dict 实际出现过的键，保证 to_dict 不补写默认值。"""
    object.__setattr__(obj, "_present", tuple(raw.keys()))


def _is_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _as_required_str(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{path} 必须是字符串，收到 {value!r}")
    return value


def _as_optional_str(value: Any, path: str) -> str | None:
    return None if value is None else _as_required_str(value, path)


def _as_bool(value: Any, path: str) -> bool:
    if isinstance(value, bool):
        return value
    if value in (0, 1):
        return bool(value)
    raise ValueError(f"{path} 必须是布尔值，收到 {value!r}")


def _as_int(value: Any, path: str) -> int:
    if _is_int(value):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    raise ValueError(f"{path} 必须是整数，收到 {value!r}")


def _as_float(value: Any, path: str) -> float:
    if not _is_number(value):
        raise ValueError(f"{path} 必须是有限数字，收到 {value!r}")
    return float(value)


def _as_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{path} 必须是数组，收到 {type(value).__name__}")
    return list(value)


def _floats(value: Any, path: str, size: int | None = None) -> tuple[float, ...]:
    items = _as_list(value, path)
    if size is not None and len(items) != size:
        raise ValueError(f"{path} 必须恰好 {size} 个数字，收到 {len(items)} 个")
    return tuple(_as_float(item, f"{path}[{i}]") for i, item in enumerate(items))


def _optional_pair(value: Any, path: str) -> tuple[float, float] | None:
    if value is None:
        return None
    pair = _floats(value, path, 2)
    return (pair[0], pair[1])


def _numeric_tuple(value: Any, path: str) -> tuple[float, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    result: list[float] = []
    for index, item in enumerate(value):
        if _is_number(item):
            result.append(float(item))
    return tuple(result)


def _pairs(value: Any, path: str) -> tuple[tuple[str, object], ...]:
    """style/view：dict 或 [key, value] 对列表 → 按键排序的冻结元组。"""
    if isinstance(value, dict):
        items: Any = value.items()
    elif isinstance(value, (list, tuple)):
        items = value
    else:
        raise ValueError(f"{path} 必须是对象或键值对数组")
    pairs: list[tuple[str, object]] = []
    for item in items:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError(f"{path} 含非法键值对：{item!r}")
        key, raw_value = item
        pairs.append((str(key), _freeze(raw_value)))
    return tuple(sorted(pairs, key=lambda pair: pair[0]))


def _build(
    cls: type,
    raw: Any,
    path: str,
    converters: dict[str, Callable[[Any, str], Any]] | None = None,
) -> Any:
    if not isinstance(raw, dict):
        raise ValueError(f"{path} 必须是对象，收到 {type(raw).__name__}")
    allowed = {item.name for item in fields(cls)}
    unknown = sorted(str(key) for key in raw if key not in allowed)
    if unknown:
        raise ValueError(f"{path} 含未知字段：{', '.join(unknown)}")
    kwargs: dict[str, Any] = {}
    for key, value in raw.items():
        if converters and key in converters:
            kwargs[key] = converters[key](value, f"{path}.{key}")
        else:
            kwargs[key] = value
    obj = cls(**kwargs)
    _set_present(obj, raw)
    return obj


def _dump_value(obj: Any, name: str, value: Any) -> Any:
    if isinstance(obj, PlotSpec) and name in {"style", "view"}:
        return {key: _thaw(item) for key, item in value}
    return _thaw(value)


def _dump_dataclass(obj: Any) -> dict:
    present = getattr(obj, "_present", None)
    if present is None:
        names = [item.name for item in fields(obj)]
    else:
        names = list(present)
    out: dict[str, Any] = {}
    for name in names:
        value = getattr(obj, name)
        if (
            isinstance(obj, FigureDocument)
            and name in {"legacy", "extensions"}
            and value is None
        ):
            continue
        if (
            isinstance(obj, FigureDocument)
            and present is None
            and name == "template"
            and value is None
        ):
            continue
        out[name] = _dump_value(obj, name, value)
    return out


def _delegate(key: str) -> Callable[..., Any]:
    fn = _DELEGATES.get(key)
    if fn is None:
        importlib.import_module("plotkit.document")
        fn = _DELEGATES.get(key)
    if fn is None:
        raise RuntimeError(f"document.model 的 {key} 委托尚未注入")
    return fn


@dataclass(frozen=True)
class Report:
    """校验结果；errors 为空即通过，warnings 不阻断。"""

    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class PageSpec:
    size: tuple[float, float] = (12.8, 8.4)
    dpi: int = 100
    margin: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    background: str = "white"
    title: str | None = None


@dataclass(frozen=True)
class AxesSpec:
    xlabel: str | None = None
    ylabel: str | None = None
    xlim: tuple[float, float] | None = None
    ylim: tuple[float, float] | None = None
    xscale: str = "linear"
    yscale: str = "linear"
    grid: bool = True
    invert_y: bool = False
    zero_line: bool = False
    ticks: tuple[float, ...] = ()
    loglabels: str = "sci"


@dataclass(frozen=True)
class ThemeRef:
    name: str = "default"
    revision: int = 0


@dataclass(frozen=True)
class TemplateRef:
    name: str
    revision: int = 0


@dataclass(frozen=True)
class NoteSpec:
    id: str
    kind: str = "text"
    text: str = ""
    color: str = "#333333"
    size: float = 12.0
    pos: tuple[float, float] = (0.0, 0.0)


@dataclass(frozen=True)
class ShapeSpec:
    id: str
    kind: str = "rect"
    rect: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)


@dataclass(frozen=True)
class PlotSpec:
    id: str
    kind: str = "line"
    x: str | None = None
    y: str | None = None
    label: str | None = None
    legend: bool = True
    style: tuple[tuple[str, object], ...] = ()
    view: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class LayerSpec:
    id: str
    rect: tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    axes: AxesSpec = field(default_factory=AxesSpec)
    plots: tuple[PlotSpec, ...] = ()
    link_to: int | None = None
    locked: bool = False
    z_order: int = 0


@dataclass(frozen=True)
class ColumnRefs:
    names: tuple[str, ...] = ()
    store: str = "default"
    version: int = 0


_PAGE_CONVERTERS: dict[str, Callable[[Any, str], Any]] = {
    "size": lambda value, path: _floats(value, path),
    "dpi": _as_int,
    "margin": lambda value, path: _floats(value, path),
    "background": _as_required_str,
    "title": _as_optional_str,
}

_AXES_CONVERTERS: dict[str, Callable[[Any, str], Any]] = {
    "xlabel": _as_optional_str,
    "ylabel": _as_optional_str,
    "xlim": _optional_pair,
    "ylim": _optional_pair,
    "xscale": _as_required_str,
    "yscale": _as_required_str,
    "grid": _as_bool,
    "invert_y": _as_bool,
    "zero_line": _as_bool,
    "ticks": _numeric_tuple,
    "loglabels": _as_required_str,
}

_THEME_CONVERTERS: dict[str, Callable[[Any, str], Any]] = {
    "name": _as_required_str,
    "revision": _as_int,
}

_TEMPLATE_CONVERTERS = dict(_THEME_CONVERTERS)

_NOTE_CONVERTERS: dict[str, Callable[[Any, str], Any]] = {
    "id": _as_required_str,
    "kind": _as_required_str,
    "text": _as_required_str,
    "color": _as_required_str,
    "size": _as_float,
    "pos": lambda value, path: _floats(value, path),
}

_SHAPE_CONVERTERS: dict[str, Callable[[Any, str], Any]] = {
    "id": _as_required_str,
    "kind": _as_required_str,
    "rect": lambda value, path: _floats(value, path),
}

_PLOT_CONVERTERS: dict[str, Callable[[Any, str], Any]] = {
    "id": _as_required_str,
    "kind": _as_required_str,
    "x": _as_optional_str,
    "y": _as_optional_str,
    "label": _as_optional_str,
    "legend": _as_bool,
    "style": _pairs,
    "view": _pairs,
}


def _tuple_of(
    cls: type,
    converter: dict[str, Callable[[Any, str], Any]] | None,
    value: Any,
    path: str,
) -> tuple[Any, ...]:
    return tuple(
        _build(cls, item, f"{path}[{i}]", converter)
        for i, item in enumerate(_as_list(value, path))
    )


_LAYER_CONVERTERS: dict[str, Callable[[Any, str], Any]] = {
    "id": _as_required_str,
    "rect": lambda value, path: _floats(value, path),
    "axes": lambda value, path: _build(AxesSpec, value, path, _AXES_CONVERTERS),
    "plots": lambda value, path: _tuple_of(PlotSpec, _PLOT_CONVERTERS, value, path),
    "link_to": lambda value, path: None if value is None else _as_int(value, path),
    "locked": _as_bool,
    "z_order": _as_int,
}

_COLUMN_CONVERTERS: dict[str, Callable[[Any, str], Any]] = {
    "names": lambda value, path: tuple(
        _as_required_str(item, f"{path}[{i}]")
        for i, item in enumerate(_as_list(value, path))
    ),
    "store": _as_required_str,
    "version": _as_int,
}

_TOP_CONVERTERS: dict[str, Callable[[Any, str], Any]] = {
    "schema": _as_required_str,
    "revision": _as_int,
    "page": lambda value, path: _build(PageSpec, value, path, _PAGE_CONVERTERS),
    "layers": lambda value, path: _tuple_of(LayerSpec, _LAYER_CONVERTERS, value, path),
    "theme": lambda value, path: _build(ThemeRef, value, path, _THEME_CONVERTERS),
    "template": lambda value, path: (
        None
        if value is None
        else _build(TemplateRef, value, path, _TEMPLATE_CONVERTERS)
    ),
    "notes": lambda value, path: _tuple_of(NoteSpec, _NOTE_CONVERTERS, value, path),
    "shapes": lambda value, path: _tuple_of(ShapeSpec, _SHAPE_CONVERTERS, value, path),
    "data": lambda value, path: _build(ColumnRefs, value, path, _COLUMN_CONVERTERS),
    "legacy": lambda value, path: None if value is None else _freeze(value),
    "extensions": lambda value, path: None if value is None else _freeze(value),
}


@dataclass(frozen=True)
class FigureDocument:
    """v1 文档根；字段顺序与 plan §4 冻结契约一致。"""

    schema: Literal["plotkit.figure/v1"] = "plotkit.figure/v1"
    revision: int = 0
    page: PageSpec = field(default_factory=PageSpec)
    layers: tuple[LayerSpec, ...] = ()
    theme: ThemeRef = field(default_factory=ThemeRef)
    template: TemplateRef | None = None
    notes: tuple[NoteSpec, ...] = ()
    shapes: tuple[ShapeSpec, ...] = ()
    data: ColumnRefs = field(default_factory=ColumnRefs)
    legacy: dict | None = None
    extensions: dict | None = None

    def to_dict(self) -> dict:
        """返回纯 JSON 可序列化 dict；legacy/extensions 缺省时省略。"""
        return _dump_dataclass(self)

    @classmethod
    def from_dict(cls, raw: dict) -> "FigureDocument":
        """严格构造：未知顶层键、错 schema 或负 revision 均抛 ValueError。"""
        if not isinstance(raw, dict):
            raise ValueError("FigureDocument.from_dict 需要 dict")
        schema = load("figure.v1.json")
        allowed = set(schema["properties"])
        required = set(schema["required"])
        unknown = sorted(str(key) for key in raw if key not in allowed)
        if unknown:
            raise ValueError(f"未知顶层字段：{', '.join(unknown)}")
        missing = sorted(required - set(raw))
        if missing:
            raise ValueError(f"缺少必填字段：{', '.join(missing)}")
        if raw.get("schema") != FIGURE_SCHEMA:
            raise ValueError(f"schema 必须为 {FIGURE_SCHEMA!r}")
        revision = raw.get("revision", 0)
        if not _is_int(revision) or revision < 0:
            raise ValueError(f"revision 必须是 >=0 的整数，收到 {revision!r}")
        kwargs = {
            key: (
                _TOP_CONVERTERS[key](value, f"FigureDocument.{key}")
                if key in _TOP_CONVERTERS
                else value
            )
            for key, value in raw.items()
        }
        obj = cls(**kwargs)
        _set_present(obj, raw)
        return obj

    @classmethod
    def migrate(cls, raw: dict) -> "FigureDocument":
        """接受 0.1 spec 或 v1 dict；0.1 先经 migrate_v0_to_v1。"""
        if not isinstance(raw, dict):
            raise ValueError("FigureDocument.migrate 需要 dict")
        if raw.get("schema") == FIGURE_SCHEMA:
            return cls.from_dict(raw)
        if raw.get("spec_version") == "0.1" or ("figure" in raw and "layers" in raw):
            migrated = _delegate("migrate")(raw)
            return cls.from_dict(migrated)
        raise ValueError("输入既不是 0.1 spec 也不是 v1 FigureDocument")

    def validate(self) -> Report:
        """行为校验；只返回 Report，绝不抛异常。"""
        errors: list[str] = []
        if self.schema != FIGURE_SCHEMA:
            errors.append(f"schema 必须为 {FIGURE_SCHEMA!r}")
        if not _is_int(self.revision) or self.revision < 0:
            errors.append("revision 必须是 >=0 的整数")
        size = tuple(self.page.size)
        if len(size) != 2 or not all(_is_number(v) and v > 0 for v in size):
            errors.append("page.size 必须恰好 2 个正数")
        if not _is_int(self.page.dpi) or self.page.dpi <= 0:
            errors.append("page.dpi 必须是正整数")
        if len(tuple(self.page.margin)) != 4 or not all(
            _is_number(v) for v in self.page.margin
        ):
            errors.append("page.margin 必须恰好 4 个有限数字")
        layer_ids = [layer.id for layer in self.layers]
        if len(layer_ids) != len(set(layer_ids)):
            errors.append("layer id 必须唯一")
        for index, layer in enumerate(self.layers):
            rect = tuple(layer.rect)
            if len(rect) != 4:
                errors.append(f"layers[{index}].rect 必须恰好 4 个数字")
            else:
                for pos, value in enumerate(rect):
                    if not _is_number(value) or not 0 <= value <= 1:
                        errors.append(
                            f"layers[{index}].rect[{pos}] 必须落在 0..1：" f"{value!r}"
                        )
            if not _is_int(layer.z_order):
                errors.append(f"layers[{index}].z_order 必须是整数")
            if layer.link_to is not None and (
                not _is_int(layer.link_to) or not 0 <= layer.link_to < len(self.layers)
            ):
                errors.append(f"layers[{index}].link_to 必须指向已有层索引或为 None")
        for label, ids in (
            ("notes", [note.id for note in self.notes]),
            ("shapes", [shape.id for shape in self.shapes]),
        ):
            if len(ids) != len(set(ids)):
                errors.append(f"{label} id 必须唯一")
        return Report(errors=tuple(errors), warnings=())

    def with_revision(self, n: int) -> "FigureDocument":
        """乐观并发：只替换 revision，保留原始键集合。"""
        updated = replace(self, revision=n)
        present = getattr(self, "_present", None)
        if present is not None:
            object.__setattr__(updated, "_present", present)
        return updated


def migrate_v0_to_v1(raw: dict) -> dict:
    """L1 模型层委托给 migrate.migrate_v0_to_v1（同层，由包初始化注入）。"""
    return _delegate("migrate")(raw)


def to_v0(doc: dict | FigureDocument) -> dict:
    """L1 模型层委托给 migrate.to_v0。"""
    return _delegate("to_v0")(doc)


def validate_document(raw: dict) -> Report:
    """L1 模型层委托给 migrate.validate_document。"""
    return _delegate("validate")(raw)


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
]
