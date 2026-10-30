"""图层能力注册表：kind → 如何变成某个后端的图元。

照搬 MultiPlotter 的形状（frozen dataclass + 单一注册入口 + 原地更新字典），但不抄它的
`draw_handler(ax, config)` 契约——那份契约字面就是 matplotlib 的 Axes，换后端等于伪造 ax。
这里每个后端各自实现 builder，注册表只负责「声明能力」。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

from ..store.registry import DataStore

Builder = Callable[[Mapping[str, Any], DataStore], Any]


@dataclass(frozen=True)
class LayerSpec:
    kind: str
    dimension: int
    builder: Builder | None
    defaults: Mapping[str, Any] = field(default_factory=dict)
    passthrough: Sequence[str] = ()
    aliases: Sequence[str] = ()
    description: str = ""
    interactive: bool = True  # False = 只出静态图，前端不给缩放/平移（D36）

    @property
    def browser_native(self) -> bool:
        """已废弃：D33 后全部走 matplotlib，保留该属性只为兼容旧调用。"""
        return self.interactive

    def validate(self) -> "LayerSpec":
        if not self.kind:
            raise ValueError("kind 不能为空")
        if self.dimension not in (2, 3):
            raise ValueError(f"dimension 必须是 2 或 3，收到 {self.dimension}")
        if isinstance(self.passthrough, str):
            raise ValueError("passthrough 不能是裸字符串")
        if self.builder is not None and not callable(self.builder):
            raise ValueError(f"{self.kind}: builder 不可调用")
        return self

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "dimension": self.dimension,
            "aliases": list(self.aliases),
            "passthrough": list(self.passthrough),
            "description": self.description,
            "interactive": self.interactive,
            "has_builder": self.builder is not None,
        }


# 全局注册表（原地更新，保证 `from plotkit.backends.registry import LAYER_SPECS` 引用一直有效）
LAYER_SPECS: dict[str, LayerSpec] = {}
ALIASES: dict[str, str] = {}


def register(
    kind: str,
    dimension: int,
    builder: Builder | None,
    *,
    defaults: Mapping[str, Any] | None = None,
    passthrough: Sequence[str] = (),
    aliases: Sequence[str] = (),
    description: str = "",
    interactive: bool = True,
    overwrite: bool = False,
) -> LayerSpec:
    if kind in LAYER_SPECS and not overwrite:
        raise ValueError(f"kind 已注册: {kind}（要覆盖请传 overwrite=True）")
    spec = LayerSpec(
        kind=kind,
        dimension=dimension,
        builder=builder,
        defaults=dict(defaults or {}),
        passthrough=tuple(passthrough),
        aliases=tuple(aliases),
        description=description,
        interactive=interactive,
    ).validate()
    LAYER_SPECS[kind] = spec
    for alias in spec.aliases:
        ALIASES[alias] = kind
    return spec


def resolve(kind: str) -> LayerSpec:
    real = ALIASES.get(kind, kind)
    if real not in LAYER_SPECS:
        raise KeyError(f"未注册的图层类型: {kind!r}（已注册: {', '.join(sorted(LAYER_SPECS))}）")
    return LAYER_SPECS[real]


def known_kind_names() -> set[str]:
    """合法 kind 名 = 注册名 + 别名（spec 里两种写法都允许，渲染时统一 resolve）。"""
    return set(LAYER_SPECS) | set(ALIASES)


def kinds() -> tuple[str, ...]:
    return tuple(sorted(LAYER_SPECS))


def describe() -> list[dict[str, Any]]:
    return [LAYER_SPECS[k].as_dict() for k in sorted(LAYER_SPECS)]
