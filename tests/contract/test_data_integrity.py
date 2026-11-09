"""数据完整性与 PKF1 JSON 列长度回归。"""

from __future__ import annotations

import pytest

from plotkit.store import frame as frame_wire
from plotkit.store.registry import DataStore


def test_dataset_values_are_read_only() -> None:
    store = DataStore()
    store.push("v", [1.0, 2.0, 3.0])
    values = store.values("v")
    assert values.flags.writeable is False
    with pytest.raises(ValueError):
        values[0] = 9.0


def test_pkf1_multiple_json_columns_roundtrip() -> None:
    columns = [
        frame_wire.FrameColumn("t", (0.0, 0.5), unit="s", role="x", encoding="f4"),
        frame_wire.FrameColumn("labels", ({"a": 1}, {"b": 2}), encoding="json", count=2),
        frame_wire.FrameColumn("v", (1.0, 2.0), unit="V", role="y", encoding="f4"),
        frame_wire.FrameColumn("meta", ({"x": 1}, {"y": 2}), encoding="json", count=2),
    ]
    decoded = frame_wire.decode_frame(frame_wire.encode_frame(columns))
    assert decoded.column_names() == ("t", "labels", "v", "meta")
    assert tuple(decoded.column("labels").values) == ({"a": 1}, {"b": 2})
    assert tuple(decoded.column("meta").values) == ({"x": 1}, {"y": 2})
    assert decoded.column("labels").byte_length > 0
