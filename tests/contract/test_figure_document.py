"""FigureDocument v1 的严格解析、冻结与行为校验。"""

from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from plotkit.document import FigureDocument, Report

MINIMAL_V1: dict[str, Any] = {
    "schema": "plotkit.figure/v1",
    "revision": 0,
    "page": {
        "size": [12.8, 8.4],
        "dpi": 100,
        "margin": [0.0, 0.0, 0.0, 0.0],
        "background": "white",
        "title": None,
    },
    "layers": [
        {
            "id": "L0",
            "rect": [0.0, 0.0, 1.0, 1.0],
            "axes": {
                "xlabel": None,
                "ylabel": None,
                "xlim": None,
                "ylim": None,
                "xscale": "linear",
                "yscale": "linear",
                "grid": True,
                "invert_y": False,
                "zero_line": False,
                "ticks": [],
                "loglabels": "sci",
            },
            "plots": [
                {
                    "id": "P0",
                    "kind": "line",
                    "x": "t",
                    "y": "v",
                    "label": "V",
                    "legend": True,
                    "style": {"width": 1.6},
                    "view": {"grid": True},
                }
            ],
            "link_to": None,
            "locked": False,
            "z_order": 0,
        }
    ],
    "theme": {"name": "default", "revision": 0},
    "notes": [],
    "shapes": [],
    "data": {
        "names": ["t", "v"],
        "store": "default",
        "version": 0,
    },
}


def _with_rect(rect: list[float]) -> dict[str, Any]:
    """复制最小文档，仅替换首层 rect。"""
    raw = copy.deepcopy(MINIMAL_V1)
    raw["layers"][0]["rect"] = rect
    return raw


def test_from_dict_round_trip() -> None:
    """严格解析后再导出，字典应逐字段一致。"""
    doc = FigureDocument.from_dict(MINIMAL_V1)
    assert doc.to_dict() == MINIMAL_V1


def test_validate_minimal_document() -> None:
    """最小合法文档通过行为校验。"""
    doc = FigureDocument.from_dict(MINIMAL_V1)
    assert doc.validate().ok is True


def test_frozen_instance_error() -> None:
    """冻结文档禁止直接改字段。"""
    doc = FigureDocument.from_dict(MINIMAL_V1)
    with pytest.raises(FrozenInstanceError):
        doc.revision = 9


def test_unknown_top_level_key_raises() -> None:
    """未知顶层字段必须被拒绝并列出键名。"""
    raw = copy.deepcopy(MINIMAL_V1)
    raw["x_extra"] = 1
    with pytest.raises(ValueError) as exc:
        FigureDocument.from_dict(raw)
    assert "x_extra" in str(exc.value)


def test_bad_rect_five_numbers_reports_error() -> None:
    """5 个数字的 rect 由 validate() 报出描述性错误。"""
    doc = FigureDocument.from_dict(_with_rect([0, 0, 1, 1, 1]))
    report = doc.validate()
    assert report.ok is False
    assert any("rect" in error for error in report.errors)


def test_bad_rect_out_of_range_reports_error() -> None:
    """越界 rect 由 validate() 报出 0..1 范围错误。"""
    doc = FigureDocument.from_dict(_with_rect([0, 0, 1.5, 1]))
    report = doc.validate()
    assert report.ok is False
    assert any("0..1" in error for error in report.errors)


def test_with_revision_bumps_only_revision() -> None:
    """乐观并发辅助只改 revision，原文档保持不变。"""
    doc = FigureDocument.from_dict(MINIMAL_V1)
    bumped = doc.with_revision(3)
    assert doc.revision == 0
    assert bumped.revision == 3
    expected = copy.deepcopy(MINIMAL_V1)
    expected["revision"] = 3
    assert bumped.to_dict() == expected


def test_report_as_dict_shape() -> None:
    """Report.as_dict() 给出稳定可序列化结构。"""
    report = Report(errors=("bad",), warnings=("warn",))
    assert report.as_dict() == {
        "ok": False,
        "errors": ["bad"],
        "warnings": ["warn"],
    }
    assert report.ok is False
    assert Report().ok is True
