"""N5 一致性契约：Selector.select_backend 为后端选择唯一入口（薄适配）。

验证三处一致：
1. ``dispatch.choose()``（含 env 解析的适配层）与 ``Selector.select_backend()``
   对同一 spec 给出相同后端；
2. ``Decision.to_header()``（X-PlotKit-Decision 响应头）里的 backend 与决策后端一致；
3. ``decision_report()`` 每行矩阵结论显式标注 ``advisory_only=True``（G3 仍不达成）。

以及 Selector 自身不读环境变量（env 解析只发生在 dispatch.choose 适配层）。
"""

from __future__ import annotations

import json

import pytest

from plotkit.backends import dispatch, selector

_SPEC_2D = {"figure": {}, "layers": [{"kind": "line"}]}
_SPEC_3D = {"figure": {}, "layers": [{"kind": "stream3d"}]}


@pytest.mark.parametrize("spec", [_SPEC_2D, _SPEC_3D])
@pytest.mark.parametrize("requested", [None, "mpl", "auto"])
def test_choose_matches_select_backend(spec, requested):
    chosen = dispatch.choose(spec, requested)
    decision = selector.Selector().select_backend(spec, requested)
    assert decision.backend == chosen
    assert decision.advisory_only is False


def test_to_header_backend_matches_decision():
    decision = selector.Selector().select_backend(_SPEC_2D, "mpl")
    header = json.loads(decision.to_header())
    assert header["backend"] == decision.backend == "mpl"
    assert header["advisory_only"] is False


def test_decision_report_rows_are_advisory_only():
    rows = selector.decision_report()
    assert rows, "能力矩阵不应为空"
    for row in rows:
        assert row["decision"]["advisory_only"] is True, row.get("id")


def test_select_backend_is_env_free(monkeypatch):
    # env 解析只发生在 dispatch.choose 适配层；Selector.select_backend 不读环境。
    monkeypatch.setenv("PLOTKIT_BACKEND", "pyvista")
    decision = selector.Selector().select_backend(_SPEC_2D, None)
    assert decision.backend == "mpl"


def test_unknown_backend_raises_consistently():
    bad = "definitely-not-a-backend"
    with pytest.raises(dispatch.BackendUnavailable):
        dispatch.choose(_SPEC_2D, bad)
    with pytest.raises(dispatch.BackendUnavailable):
        selector.Selector().select_backend(_SPEC_2D, bad)
