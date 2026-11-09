"""渲染策略选择：Decision / RenderTarget / Backend / Selector。

能力矩阵是「可声明、可枚举、可回归」的首选判断点。

N5（G3 单一决策点，行为保持型薄适配）：``backends/dispatch.choose()`` 已收敛为
``Selector.select_backend()`` 的薄适配层——真实算法仍在 dispatch ``_choose_impl``，
但对外唯一边界是 Selector。**G3 仍不达成**：``RendererSelector.render`` / hybrid3d /
pyvista pool 等渲染路径尚未证明全部经此单点，故 ``Selector`` 的矩阵结论目前仅作
advisory（见 ``decision_report`` 的 ``advisory_only=True``）。

约束（计划 §10 X6）：Selector 自身不读任何环境变量（``PLOTKIT_BACKEND`` 等解析留在
dispatch.choose() 适配层）；显式 backend 仅用于调试且强制 ``degraded=True``。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, Protocol, Sequence

_MATRIX_FILE = Path(__file__).resolve().parents[1] / "schema" / "capability_matrix.json"

Quality = Literal["draft", "balanced", "publication"]
TargetKind = Literal["export", "viewport", "web"]


@dataclass(frozen=True)
class RenderTarget:
    kind: TargetKind = "export"
    fmt: str = "png"
    width: int = 900
    height: int = 520
    dpi: int = 100
    xlim: tuple[float, float] | None = None
    ylim: tuple[float, float] | None = None
    quality: Quality = "balanced"


@dataclass(frozen=True)
class Decision:
    backend: str
    reason: str
    fallback: str | None = None
    capabilities_used: tuple[str, ...] = ()
    degraded: bool = False
    advisory_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "backend": self.backend,
            "reason": self.reason,
            "fallback": self.fallback,
            "capabilities_used": list(self.capabilities_used),
            "degraded": self.degraded,
            "advisory_only": self.advisory_only,
        }

    def to_header(self) -> str:
        """供 ``X-PlotKit-Decision`` 使用；ASCII-only，HTTP header 安全。"""
        return json.dumps(
            self.to_dict(), sort_keys=True, ensure_ascii=True, separators=(",", ":")
        )


class Backend(Protocol):
    name: str
    version: str
    capabilities: frozenset[str]

    def supports(self, doc: Any, target: RenderTarget) -> Decision: ...

    def render(self, doc: Any, store: Any, target: RenderTarget) -> Any: ...


def capability_matrix() -> dict[str, Any]:
    """返回完整的能力矩阵声明（含 schema / revision / rows）。"""
    raw = json.loads(_MATRIX_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("capability_matrix.json 顶层必须是对象")
    return raw


def capability_rows() -> list[dict[str, Any]]:
    """直接读 L0 的 JSON，避免 import 触发任何绘制后端。"""
    rows = capability_matrix().get("rows")
    if not isinstance(rows, list):
        raise ValueError("capability_matrix.json 缺少 rows 数组")
    return rows


# 图层 kind → 语义特征。未知的 kind 一律归入 2d，保证决策不会静默丢能力。
_KIND_FEATURES: dict[str, str] = {
    "lic": "vector-field",
    "quiver": "vector-field",
    "streamplot": "vector-field",
    "vector_field": "vector-field",
    "ns_vortex": "ns",
    "ns": "ns",
    "anim": "animation",
    "animation": "animation",
}
_LARGE_THRESHOLD = 1_000_000
_ANIMATION_FORMATS = frozenset({"gif", "mp4", "zip"})


def doc_features(doc: Any, target: RenderTarget | None = None) -> frozenset[str]:
    """从文档（dict 或对象）派生能力特征；显式 ``features`` 优先。"""
    explicit: Any = None
    if isinstance(doc, Mapping):
        explicit = doc.get("features")
    elif doc is not None:
        explicit = getattr(doc, "features", None)
    if explicit is not None:
        features = {str(item) for item in explicit}
    else:
        features = set()
        layers: Sequence[Any] = ()
        if isinstance(doc, Mapping):
            layers = tuple(doc.get("layers") or ())
        elif doc is not None:
            layers = tuple(getattr(doc, "layers", ()) or ())
        for layer in layers:
            kind = ""
            if isinstance(layer, Mapping):
                kind = str(layer.get("kind", "")).lower()
            else:
                kind = str(getattr(layer, "kind", "")).lower()
            if not kind:
                continue
            if "3d" in kind or "volume" in kind or "mesh" in kind:
                features.add("3d")
            hint = _KIND_FEATURES.get(kind)
            if hint:
                features.add(hint)
            if kind in ("line", "scatter", "errorbar", "timeseries"):
                features.add("timeseries")
        npoints = 0
        if isinstance(doc, Mapping):
            npoints = int(doc.get("npoints") or 0)
        elif doc is not None:
            npoints = int(getattr(doc, "npoints", 0) or 0)
        if npoints >= _LARGE_THRESHOLD:
            features.add("large")
        if isinstance(doc, Mapping) and doc.get("streaming"):
            features.add("live")
        if not features:
            features.add("2d")
        if "2d" not in features and "3d" not in features and "ns" not in features:
            features.add("2d")
    if target is not None and target.fmt.lower() in _ANIMATION_FORMATS:
        features.add("animation")
    return frozenset(features)


def _row_score(
    row: Mapping[str, Any], index: int, features: frozenset[str], target: RenderTarget
) -> tuple[int, int, int, int] | None:
    match = row.get("match") or {}
    required = frozenset(str(item) for item in match.get("doc_features") or ())
    if not required.issubset(features):
        return None
    kinds = frozenset(str(item) for item in match.get("target_kinds") or ())
    if kinds and "*" not in kinds and target.kind not in kinds:
        return None
    formats = frozenset(str(item).lower() for item in match.get("formats") or ())
    if formats and "*" not in formats and target.fmt.lower() not in formats:
        return None
    qualities = frozenset(str(item) for item in match.get("qualities") or ())
    if qualities and "*" not in qualities and target.quality not in qualities:
        return None
    return (
        len(required),
        0 if "*" in formats else 1,
        0 if "*" in qualities else 1,
        -index,
    )


class Selector:
    """能力矩阵驱动的唯一决策点。"""

    def __init__(
        self,
        rows: Sequence[Mapping[str, Any]] | None = None,
        *,
        available: Mapping[str, bool] | None = None,
        policy: str = "quality",
    ) -> None:
        self.rows: list[dict[str, Any]] = list(
            rows if rows is not None else capability_rows()
        )
        self.available: dict[str, bool] = dict(available or {})
        self.policy = policy

    def select(
        self,
        doc: Any,
        target: RenderTarget,
        *,
        backend: str | None = None,
        policy: str | None = None,
    ) -> Decision:
        # 调试显式指定：X6 要求 degraded=True，且不经任何矩阵判断。
        if backend is not None:
            return Decision(
                backend=str(backend),
                reason=f"调试显式指定后端 {backend}；按 X6 强制 degraded=True",
                fallback=None,
                capabilities_used=(),
                degraded=True,
            )
        active_policy = policy or self.policy
        features = doc_features(doc, target)
        best: tuple[tuple[int, int, int, int], dict[str, Any]] | None = None
        for index, row in enumerate(self.rows):
            score = _row_score(row, index, features, target)
            if score is None:
                continue
            if active_policy in ("draft", "speed") and row.get("match", {}).get(
                "requires_extra"
            ):
                continue
            if best is None or score > best[0]:
                best = (score, dict(row))
        if best is None:
            return Decision(
                backend="mpl",
                reason="未命中任何能力行，回落到 mpl 2D 基线（非降级）",
                fallback=None,
                capabilities_used=("mpl2d",),
                degraded=False,
            )
        row = best[1]
        row_id = str(row.get("id", ""))
        extra = row.get("match", {}).get("requires_extra")
        if extra and not self.available.get(str(extra), False):
            fallback = str(row.get("fallback") or "mpl")
            return Decision(
                backend=fallback,
                reason=(
                    f"能力行 {row_id} 需要 extra {extra}，当前不可用；"
                    f"降级到 {fallback}（降级可观测，不静默）"
                ),
                fallback=fallback,
                capabilities_used=tuple(row.get("capabilities_used") or ()),
                degraded=True,
            )
        return Decision(
            backend=str(row.get("backend", "mpl")),
            reason=f"命中能力行 {row_id}：{row.get('situation', '')}；policy={active_policy}",
            fallback=row.get("fallback"),
            capabilities_used=tuple(row.get("capabilities_used") or ()),
            degraded=False,
        )

    def select_backend(
        self, spec: Mapping[str, Any], requested: str | None = None
    ) -> Decision:
        """薄适配：把 dispatch 既有的后端选择算法收敛到 Selector 这一唯一入口。

        - **不改变任何后端选择语义**：内部委托 ``dispatch._choose_impl``。
        - 遵守本模块约束：本方法**不读环境变量**；``PLOTKIT_BACKEND`` 等环境解析
          留在 ``dispatch.choose()`` 适配层完成后作为 ``requested`` 传入。
        - **G3 仍不达成**：``RendererSelector.render`` / hybrid3d / pyvista pool 等
          路径尚未证明全部经此单点，故本决策仅作统一入口，不做矩阵驱动的真实切换。
        """
        from . import dispatch

        backend = dispatch._choose_impl(spec, requested)
        return Decision(
            backend=backend,
            reason="由 Selector.select_backend 统一决策（薄适配 dispatch 既有算法）",
            advisory_only=False,
        )


def select(
    doc: Any,
    target: RenderTarget,
    *,
    policy: str = "quality",
    backend: str | None = None,
    available: Mapping[str, bool] | None = None,
) -> Decision:
    return Selector(available=available, policy=policy).select(
        doc, target, backend=backend, policy=policy
    )


def decision_report(
    available: Mapping[str, bool] | None = None,
) -> list[dict[str, Any]]:
    """对能力矩阵每一行产出一条可回归的 Decision（供 reports/decisions.json）。"""
    extras = {"three": True, "ns": True, **(available or {})}
    selector = Selector(available=extras)
    report: list[dict[str, Any]] = []
    for row in selector.rows:
        match = row.get("match") or {}
        kinds = list(match.get("target_kinds") or ["export"])
        formats = [item for item in (match.get("formats") or ["png"]) if item != "*"]
        qualities = [
            item for item in (match.get("qualities") or ["balanced"]) if item != "*"
        ]
        target = RenderTarget(
            kind=kinds[0] if kinds else "export",
            fmt=formats[0] if formats else "png",
            quality=qualities[0] if qualities else "balanced",
        )
        doc: dict[str, Any] = {"features": sorted(match.get("doc_features") or [])}
        decision = selector.select(doc, target)
        report.append(
            {
                "id": row.get("id"),
                "situation": row.get("situation"),
                "target": {
                    "kind": target.kind,
                    "fmt": target.fmt,
                    "quality": target.quality,
                },
                "doc_features": doc["features"],
                "decision": {**decision.to_dict(), "advisory_only": True},
                "acceptance": row.get("acceptance"),
            }
        )
    return report
