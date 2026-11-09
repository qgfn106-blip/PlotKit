"""0.1 fixture 的黄金双向迁移与未知字段守恒。"""

from __future__ import annotations

import copy
import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from plotkit.document import (
    FigureDocument,
    migrate_v0_to_v1,
    to_v0,
    validate_document,
)
from plotkit.spec.model import new_spec

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURES = (
    "spec_v0_minimal.json",
    "spec_v0_rich.json",
    "spec_v0_unknown_fields.json",
)


def _load(name: str) -> dict[str, Any]:
    """按 UTF-8 读取一份 0.1 fixture。"""
    path = FIXTURE_DIR / name
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", FIXTURES)
def test_migration_golden_roundtrip(name: str) -> None:
    """迁移、校验、反迁移、文档化四步都不丢字段。"""
    raw = _load(name)
    snapshot = copy.deepcopy(raw)
    migrated = migrate_v0_to_v1(raw)
    assert raw == snapshot

    migrated_snapshot = copy.deepcopy(migrated)
    assert validate_document(migrated).ok is True
    assert to_v0(migrated) == raw
    assert migrated == migrated_snapshot

    doc = FigureDocument.migrate(raw)
    assert doc.schema == "plotkit.figure/v1"
    assert doc.revision == 0
    assert to_v0(doc.to_dict()) == raw
    assert validate_document(doc.to_dict()).ok is True
    with pytest.raises(FrozenInstanceError):
        doc.revision = 5


@pytest.mark.parametrize("name", FIXTURES)
def test_v1_dict_migrate_is_idempotent(name: str) -> None:
    """把 v1 dict 再交给 migrate 应得到等价文档。"""
    raw = _load(name)
    migrated = migrate_v0_to_v1(raw)
    doc = FigureDocument.migrate(migrated)
    assert doc.to_dict() == migrated
    assert to_v0(doc.to_dict()) == raw


def test_unknown_fields_survive() -> None:
    """未知顶层 / figure / layer 字段进入 extensions 且可反迁。"""
    raw = _load("spec_v0_unknown_fields.json")
    migrated = migrate_v0_to_v1(raw)
    ext = migrated["extensions"]

    top_value = raw["x_experiment"]
    figure_value = raw["figure"]["x_origin_template"]
    layer_field = raw["layers"][0]["x_custom_marker"]
    assert ext["unknown_top"]["x_experiment"] == top_value
    assert ext["x_experiment"] == top_value
    assert ext["unknown_figure"]["x_origin_template"] == figure_value
    assert ext["x_origin_template"] == figure_value
    nested = ext["unknown_layers"][0]["fields"]
    assert nested["x_custom_marker"] == layer_field
    assert ext["x_custom_marker"] == layer_field

    restored = to_v0(migrated)
    assert restored == raw
    assert restored["x_experiment"] == top_value
    assert restored["figure"]["x_origin_template"] == figure_value
    assert restored["layers"][0]["x_custom_marker"] == layer_field


def test_real_new_spec_mapping() -> None:
    """真实 new_spec() 形状按字段映射到 page / theme。"""
    raw = new_spec(size=(9.6, 5.4), dpi=144, theme="solar", title="demo")
    migrated = migrate_v0_to_v1(raw)
    assert migrated["page"]["dpi"] == 144
    assert migrated["page"]["size"] == [9.6, 5.4]
    assert migrated["theme"]["name"] == "solar"
    assert migrated["page"]["title"] == "demo"
    assert validate_document(migrated).ok is True

    doc = FigureDocument.migrate(raw)
    assert doc.page.dpi == 144
    assert doc.page.size == (9.6, 5.4)
    assert doc.theme.name == "solar"
    assert doc.page.title == "demo"
    assert to_v0(doc.to_dict()) == raw
