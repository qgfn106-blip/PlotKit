"""数据完整性与 PKF1 JSON 列长度回归。"""

from __future__ import annotations

import json
import struct
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from plotkit.store import downsample
from plotkit.store import frame as frame_wire
from plotkit.store.registry import DATA_LOCK, DataStore


def test_dataset_values_are_read_only() -> None:
    store = DataStore()
    store.push("v", [1.0, 2.0, 3.0])
    values = store.values("v")
    assert values.flags.writeable is False
    with pytest.raises(ValueError):
        values[0] = 9.0


def test_pyramid_cache_invalidated_on_push(monkeypatch) -> None:
    monkeypatch.setattr(downsample, "PYRAMID_MIN_POINTS", 2)
    store = DataStore()
    store.add("x", list(range(8)))
    store.add("y", list(range(8)))
    first = store.pyramid("x", "y")
    assert first is not None
    assert store.pyramid("x", "y") is first

    store.push("y", [99])
    second = store.pyramid("x", "y")
    assert second is not None
    assert second is not first


def test_pyramid_cache_invalidated_on_overwrite(monkeypatch) -> None:
    monkeypatch.setattr(downsample, "PYRAMID_MIN_POINTS", 2)
    store = DataStore()
    store.add("x", list(range(8)))
    store.add("y", list(range(8)))
    first = store.pyramid("x", "y")
    store.add("y", list(range(8, 16)), overwrite=True)
    second = store.pyramid("x", "y")
    assert second is not None
    assert second is not first


def test_pyramid_removed_with_dataset(monkeypatch) -> None:
    monkeypatch.setattr(downsample, "PYRAMID_MIN_POINTS", 2)
    store = DataStore()
    store.add("x", list(range(8)))
    store.add("y", list(range(8)))
    assert store.pyramid("x", "y") is not None
    store.remove("y")
    with pytest.raises(KeyError):
        store.pyramid("x", "y")


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


def test_pyramid_cache_invalidated_on_trim(monkeypatch) -> None:
    monkeypatch.setattr(downsample, "PYRAMID_MIN_POINTS", 2)
    store = DataStore()
    store.add("x", list(range(8)))
    store.add("y", list(range(8)))
    first = store.pyramid("x", "y")
    assert first is not None
    store.trim("y", 4)
    second = store.pyramid("x", "y")
    assert second is not None
    assert second is not first


def test_large_frame_roundtrip_from_store_preserves_boundary() -> None:
    n = 200_000
    store = DataStore()
    store.add("t", list(range(n)))
    store.add("v", [index * 0.5 for index in range(n)])
    decoded = frame_wire.decode_frame(
        frame_wire.encode_frame_from_store(store, ["t", "v"], generation=9)
    )
    assert decoded.generation == 9
    assert decoded.column("t").count == n
    assert decoded.column("v").count == n
    assert decoded.column("t").values[-1] == n - 1
    assert decoded.column("v").values[-1] == (n - 1) * 0.5
    assert len(decoded.payload) == n * 8 + n * 8


def test_encode_frame_from_store_snapshot_is_consistent_under_push() -> None:
    store = DataStore()
    store.add("t", [0.0])
    store.add("v", [0.0])
    stop = threading.Event()

    def writer() -> None:
        for index in range(1, 3000):
            if stop.is_set():
                return
            with DATA_LOCK:
                store.push("t", [float(index)])
                store.push("v", [float(index)])

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(writer)
        try:
            for _ in range(30):
                decoded = frame_wire.decode_frame(
                    frame_wire.encode_frame_from_store(store, ["t", "v"])
                )
                times = tuple(decoded.column("t").values)
                values = tuple(decoded.column("v").values)
                assert len(times) == len(values)
                assert times == values
        finally:
            stop.set()
            future.result(timeout=5)
