"""后端选择器契约：值对象冻结、header 可解析、特征推导、降级与 policy。"""

from __future__ import annotations

import dataclasses
import json

import pytest

from plotkit.backends.selector import (
    Decision,
    RenderTarget,
    Selector,
    capability_rows,
    doc_features,
    select,
)


def test_render_target_and_decision_are_frozen():
    target = RenderTarget()
    assert target.kind == "export"
    assert target.fmt == "png"
    assert target.quality == "balanced"
    with pytest.raises(dataclasses.FrozenInstanceError):
        target.fmt = "svg"
    decision = Decision("mpl", "reason")
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.backend = "canvas"


def test_decision_header_is_ascii_and_json_parsable():
    decision = Decision(
        "mpl",
        "调试原因",
        fallback="canvas",
        capabilities_used=("mpl2d", "svg-text"),
        degraded=True,
    )
    header = decision.to_header()
    assert isinstance(header, str)
    header.encode("ascii")
    payload = json.loads(header)
    assert payload == decision.to_dict()
    assert payload["backend"] == "mpl"
    assert payload["degraded"] is True
    assert payload["capabilities_used"] == ["mpl2d", "svg-text"]


def test_doc_features_derive_3d_vector_field_animation_and_large():
    assert "3d" in doc_features({"layers": [{"kind": "mesh3d"}]})
    assert "vector-field" in doc_features({"layers": [{"kind": "quiver"}]})
    assert "animation" in doc_features({"features": ["2d"]}, RenderTarget(fmt="gif"))
    assert "large" in doc_features({"layers": [{"kind": "line"}], "npoints": 2_000_000})
    assert "2d" in doc_features({})
    assert "3d" in doc_features({"features": ["3d"]})


def test_debug_backend_override_forces_degraded():
    decision = select(
        {"features": ["3d"]},
        RenderTarget(kind="export", fmt="svg", quality="balanced"),
        backend="mpl",
    )
    assert decision.backend == "mpl"
    assert decision.degraded is True


def test_missing_three_extra_degrades_with_fallback():
    doc = {"features": ["3d"]}
    target = RenderTarget(kind="export", fmt="svg", quality="balanced")
    degraded = select(doc, target, available={"three": False, "ns": False})
    assert degraded.degraded is True
    assert degraded.backend == "mpl"
    assert degraded.fallback == "mpl"
    healthy = select(doc, target, available={"three": True, "ns": True})
    assert healthy.degraded is False
    assert healthy.backend == "hybrid3d"


def test_no_row_match_falls_back_to_mpl_without_degradation():
    decision = select(
        {"features": ["__unknown__"]},
        RenderTarget(kind="export", fmt="jpeg", quality="draft"),
    )
    assert decision.backend == "mpl"
    assert decision.degraded is False
    assert decision.fallback is None


def test_draft_policy_skips_extra_requiring_rows():
    doc = {"features": ["3d"]}
    target = RenderTarget(kind="export", fmt="svg", quality="balanced")
    draft = select(doc, target, policy="draft", available={"three": True, "ns": True})
    assert draft.backend == "mpl"
    assert draft.degraded is False
    assert draft.fallback is None
    quality = select(
        doc, target, policy="quality", available={"three": True, "ns": True}
    )
    assert quality.backend == "hybrid3d"


def test_selector_with_custom_rows_uses_those_rows():
    rows = capability_rows()
    selector = Selector(rows, available={"three": True, "ns": True})
    decision = selector.select(
        {"features": ["3d"]}, RenderTarget(kind="export", fmt="svg", quality="balanced")
    )
    assert decision.backend == "hybrid3d"
    assert decision.degraded is False

    empty = Selector([], available={"three": True, "ns": True})
    fallback = empty.select({"features": ["2d"]}, RenderTarget())
    assert fallback.backend == "mpl"
    assert fallback.degraded is False
