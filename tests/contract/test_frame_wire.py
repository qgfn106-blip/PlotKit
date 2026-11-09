"""frame/v1 线格式契约：golden vector、往返、异常输入、并发一致性。"""

from __future__ import annotations

import hashlib
import json
import struct
from concurrent.futures import ThreadPoolExecutor

import pytest

from plotkit.store import frame as frame_wire
from plotkit.store.registry import DATA_LOCK, DataStore

GOLDEN_SHA256 = "7a457743abeac90b9351a4694326087b1b35ca17ad6a028c3c6ac3449293f175"
GOLDEN_LENGTH = 314


def _columns() -> list[frame_wire.FrameColumn]:
    return [
        frame_wire.FrameColumn(
            "t", (0.0, 0.5, 1.0), unit="s", role="x", dtype="float32", encoding="f4"
        ),
        frame_wire.FrameColumn(
            "v_out", (1.0, 2.0, 3.0), unit="V", role="y", dtype="float32", encoding="f4"
        ),
    ]


def test_golden_vector_is_frozen():
    blob = frame_wire.frame_golden_vector()
    assert isinstance(blob, bytes)
    assert len(blob) == GOLDEN_LENGTH
    assert hashlib.sha256(blob).hexdigest() == GOLDEN_SHA256
    decoded = frame_wire.decode_frame(blob)
    assert decoded.schema == frame_wire.frame_schema_id()
    assert decoded.column_names() == ("t", "v_out")
    assert tuple(decoded.column("t").values) == (0.0, 0.5, 1.0)


def test_encode_decode_roundtrip_preserves_metadata():
    columns = _columns()
    blob = frame_wire.encode_frame(
        columns,
        generation=11,
        cursor=3,
        t0=1.25,
        dt=0.25,
        version=7,
    )
    decoded = frame_wire.decode_frame(blob)
    assert decoded.schema == frame_wire.frame_schema_id()
    assert decoded.generation == 11
    assert decoded.cursor == 3
    assert decoded.t0 == 1.25
    assert decoded.dt == 0.25
    assert decoded.version == 7
    assert decoded.column_names() == ("t", "v_out")
    for original in columns:
        got = decoded.column(original.name)
        assert tuple(got.values) == tuple(original.values)
        assert got.unit == original.unit
        assert got.role == original.role
        assert got.dtype == original.dtype
        assert got.encoding == original.encoding
        assert got.count == len(original.values)
    assert isinstance(decoded.to_dict(), dict)


def test_encode_frame_from_store_with_real_datastore():
    store = DataStore()
    store.add("t", [0.0, 0.5, 1.0], unit="s", role="coord")
    store.add("v", [1.0, 2.0, 3.0], unit="V", role="series")
    blob = frame_wire.encode_frame_from_store(store, ["t", "v"], generation=4, dt=0.5)
    decoded = frame_wire.decode_frame(blob)
    assert decoded.generation == 4
    assert decoded.column_names() == ("t", "v")
    assert decoded.column("t").unit == "s"
    assert decoded.column("v").role == "series"
    assert tuple(decoded.column("v").values) == (1.0, 2.0, 3.0)

    store.push("v", [9.0])
    grown = frame_wire.decode_frame(frame_wire.encode_frame_from_store(store, ["v"]))
    assert grown.column("v").count == 4
    assert tuple(grown.column("v").values) == (1.0, 2.0, 3.0, 9.0)


def test_corrupt_frames_raise_value_error():
    golden = frame_wire.frame_golden_vector()

    # 1) magic 被改写
    with pytest.raises(ValueError):
        frame_wire.decode_frame(b"XXXX" + golden[4:])

    # 2) payload 被截断一个字节
    with pytest.raises(ValueError):
        frame_wire.decode_frame(golden[:-1])

    # 3) header 声明的 count 与实际 payload 不符
    (size,) = struct.unpack_from("<I", golden, 4)
    header = json.loads(golden[8 : 8 + size].decode("utf-8"))
    header["columns"][0]["count"] = 999
    packed = json.dumps(
        header, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    bad_count = (
        frame_wire.FRAME_MAGIC
        + struct.pack("<I", len(packed))
        + packed
        + golden[8 + size :]
    )
    with pytest.raises(ValueError):
        frame_wire.decode_frame(bad_count)


def test_concurrent_encode_decode_has_no_length_mismatch():
    columns = _columns()
    baseline = frame_wire.decode_frame(frame_wire.encode_frame(columns))
    expected_payload_length = len(baseline.payload)
    expected_counts = [len(column.values) for column in columns]

    def one(index: int) -> bool:
        with DATA_LOCK:
            blob = frame_wire.encode_frame(columns, generation=index, cursor=3)
            decoded = frame_wire.decode_frame(blob)
        (header_size,) = struct.unpack_from("<I", blob, 4)
        counts = [decoded.column(column.name).count for column in columns]
        lengths = [len(decoded.column(column.name).values) for column in columns]
        return (
            len(decoded.payload) == expected_payload_length
            and len(blob) == 8 + header_size + len(decoded.payload)
            and counts == expected_counts
            and lengths == expected_counts
            and decoded.generation == index
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(one, range(1000)))
    assert len(results) == 1000
    assert all(results)
