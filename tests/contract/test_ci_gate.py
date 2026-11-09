# -*- coding: utf-8 -*-
"""裁定 ⑨-5：/api/capabilities 的 decisions 与 reports/decisions.json 逐字段一致。

两边都走 ``decision_report(available=...)``；给定同一个 available 映射
（``{"three": True, "ns": True}``），运行时端点与报告必须逐字段一致。
报告是「理想环境重放」快照，不是运行时采样，故同时校验其 environment 标注。
只通过公开 HTTP API + 报告 JSON 断言，不读源码字符串、不碰私有符号。
"""
from __future__ import annotations

import json
from pathlib import Path

import plotkit as pk
import pytest
from fastapi.testclient import TestClient

from plotkit.server import app as app_module

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "reports" / "decisions.json"

# 与 tools/check_capability_matrix.py / generate_reports.py 钉定的理想环境一致。
ALL_EXTRAS = {"three": True, "ns": True}
ENVIRONMENT = "all-extras-available (synthetic)"

_DECISION_FIELDS = (
    "backend",
    "reason",
    "fallback",
    "capabilities_used",
    "degraded",
)
_ROW_FIELDS = ("id", "situation", "doc_features", "target", "acceptance")


def test_capabilities_decisions_match_report_field_by_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert REPORT.is_file(), f"缺少决策报告 {REPORT}；先运行 generate_reports.py"
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    assert report.get("environment") == ENVIRONMENT
    rows = report["rows"]
    assert len(rows) == 8

    fig = pk.figure(title="ci-gate")
    fig.add_data("t", [0, 1, 2], role="coord")
    fig.add_data("v", [1, 2, 3], role="series")
    fig.add_plot(x="t", y="v", label="v")

    # 把运行时 probe 的 optional 钉成与报告相同的 available 映射。
    monkeypatch.setattr(
        app_module.host_api,
        "probe",
        lambda: {"optional": dict(ALL_EXTRAS)},
    )
    client = TestClient(app_module.create_app(fig, layout_path=tmp_path / "ui.json"))
    response = client.get("/api/capabilities")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    payload = response.json()
    decisions = payload["decisions"]
    assert len(decisions) == len(rows) == 8

    for index, (live, frozen) in enumerate(zip(decisions, rows)):
        # 逐字段比对行元数据。
        for field in _ROW_FIELDS:
            assert live[field] == frozen[field], f"row {index} 字段 {field} 不一致"
        # 逐字段比对 Decision 本体（裁定 ⑨-5 的核心）。
        live_decision = live["decision"]
        frozen_decision = frozen["decision"]
        assert set(live_decision) == set(
            frozen_decision
        ), f"row {index} Decision 字段集合不一致"
        for field in _DECISION_FIELDS:
            assert (
                live_decision[field] == frozen_decision[field]
            ), f"row {index} Decision.{field} 不一致"
        # 理想环境重放：8 行都不应降级。
        assert frozen_decision["degraded"] is False
