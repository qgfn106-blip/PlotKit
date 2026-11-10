"""数据完整性与 PKF1 JSON 列长度回归。"""

from __future__ import annotations

import json
import struct

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


def _frame_without_byte_length(columns, column_index: int) -> bytes:
    data = frame_wire.encode_frame(columns)
    (header_len,) = struct.unpack_from("<I", data, 4)
    header = json.loads(data[8 : 8 + header_len].decode("utf-8"))
    header["columns"][column_index].pop("byte_length", None)
    header_bytes = json.dumps(
        header, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return b"PKF1" + struct.pack("<I", len(header_bytes)) + header_bytes + data[8 + header_len :]


def test_pkf1_legacy_json_column_with_following_columns_is_rejected() -> None:
    columns = [
        frame_wire.FrameColumn("labels", ({"a": 1},), encoding="json", count=1),
        frame_wire.FrameColumn("v", (1.0,), unit="V", role="y", encoding="f4"),
    ]
    with pytest.raises(ValueError, match="旧格式 JSON 列必须是最后一列"):
        frame_wire.decode_frame(_frame_without_byte_length(columns, 0))


def test_pkf1_legacy_json_last_column_remains_compatible() -> None:
    columns = [
        frame_wire.FrameColumn("v", (1.0,), unit="V", role="y", encoding="f4"),
        frame_wire.FrameColumn("meta", ({"x": 1},), encoding="json", count=1),
    ]
    decoded = frame_wire.decode_frame(_frame_without_byte_length(columns, 1))
    assert tuple(decoded.column("meta").values) == ({"x": 1},)
