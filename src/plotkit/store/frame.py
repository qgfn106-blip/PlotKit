"""Frame v1 wire：单一 encode/decode 出口（P0 契约冻结，纯新增）。

与旧的 ``PK01`` 系列互不干扰：``/api/column``、``/api/xyz``、``/api/segments``
等既有路由保持原样，本模块只提供一条新的、可回归的线格式。

wire 形状（小端，平台无关）::

    b"PKF1" | uint32 header_len | header_json(UTF-8) | payload

header 为 sort_keys 的 JSON，含 schema / generation / cursor / t0 / dt /
version / columns[]；每个 column 描述 name / unit / role / dtype /
encoding / offset / count，``offset`` 是相对 payload 起点的字节偏移。
payload 是各列原始字节按 columns 顺序拼接。

层依赖：L2（store）只允许依赖 L0（schema 的 JSON 文件），不 import 任何
plotkit Python 模块，也不 import backends / server / api。
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

FRAME_SCHEMA_FALLBACK = "plotkit.frame/v1"
FRAME_MAGIC = b"PKF1"
_HEADER_LEN = struct.Struct("<I")
_SCHEMA_FILE = Path(__file__).resolve().parents[1] / "schema" / "frame.v1.json"

# encoding → numpy dtype string（显式小端，规避平台字节序差异）
_ENCODINGS: dict[str, str] = {
    "f2": "<f2",
    "f4": "<f4",
    "f8": "<f8",
    "i1": "|i1",
    "i2": "<i2",
    "i4": "<i4",
    "i8": "<i8",
    "u1": "|u1",
    "u2": "<u2",
    "u4": "<u4",
    "u8": "<u8",
    "json": "json",
}


def frame_schema_id() -> str:
    """从 L0 的 frame.v1.json 取 schema id（文件缺失时退到常量）。"""
    try:
        raw = json.loads(_SCHEMA_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return FRAME_SCHEMA_FALLBACK
    candidates = (
        raw.get("$id"),
        (raw.get("properties") or {}).get("schema", {}).get("const"),
        FRAME_SCHEMA_FALLBACK,
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.startswith("plotkit.frame/"):
            return candidate
    return FRAME_SCHEMA_FALLBACK


@dataclass(frozen=True)
class FrameColumn:
    """一列数据；``offset`` / ``count`` 由 encode_frame 填充。"""

    name: str
    values: tuple[Any, ...] = ()
    unit: str = ""
    role: str = "auto"
    dtype: str = "float32"
    encoding: str = "f4"
    offset: int = 0
    count: int = 0
    #: JSON 列的实际字节长度；非 JSON 列由 encoding/count 推出，保持旧 wire 不变。
    byte_length: int = 0

    def descriptor(self) -> dict[str, Any]:
        item = {
            "name": self.name,
            "unit": self.unit,
            "role": self.role,
            "dtype": self.dtype,
            "encoding": self.encoding,
            "offset": self.offset,
            "count": self.count,
        }
        if self.byte_length:
            item["byte_length"] = self.byte_length
        return item


@dataclass(frozen=True)
class Frame:
    """解码后的 Frame v1 对象（不可变）。"""

    schema: str
    generation: int
    cursor: int
    t0: float
    dt: float
    version: int
    columns: tuple[FrameColumn, ...]
    payload: bytes

    def column_names(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)

    def column(self, name: str) -> FrameColumn:
        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(f"Frame 中没有列 {name!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "generation": self.generation,
            "cursor": self.cursor,
            "t0": self.t0,
            "dt": self.dt,
            "version": self.version,
            "columns": [column.descriptor() for column in self.columns],
        }


def _encode_values(values: Sequence[Any], encoding: str) -> bytes:
    if encoding == "json":
        return json.dumps(
            list(values), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
    if encoding not in _ENCODINGS:
        raise ValueError(f"不支持的 encoding {encoding!r}")
    array = np.asarray(list(values), dtype=np.dtype(_ENCODINGS[encoding]))
    return array.tobytes()


def _decode_values(blob: bytes, encoding: str, count: int) -> tuple[Any, ...]:
    if encoding == "json":
        return tuple(json.loads(blob.decode("utf-8")))
    if encoding not in _ENCODINGS:
        raise ValueError(f"不支持的 encoding {encoding!r}")
    array = np.frombuffer(blob, dtype=np.dtype(_ENCODINGS[encoding]), count=count)
    return tuple(array.tolist())


def encode_frame(
    columns: Iterable[FrameColumn],
    *,
    generation: int = 0,
    cursor: int = 0,
    t0: float = 0.0,
    dt: float = 0.0,
    version: int = 0,
    schema: str | None = None,
) -> bytes:
    """把若干列编码成 Frame v1 wire；同一输入逐字节可复现。"""
    blobs: list[bytes] = []
    described: list[FrameColumn] = []
    offset = 0
    seen: set[str] = set()
    for column in columns:
        if not column.name:
            raise ValueError("列名不能为空")
        if column.name in seen:
            raise ValueError(f"重复列名 {column.name!r}")
        seen.add(column.name)
        blob = _encode_values(column.values, column.encoding)
        described.append(
            replace(
                column,
                values=(),
                offset=offset,
                count=len(column.values),
                byte_length=len(blob) if column.encoding == "json" else 0,
            )
        )
        blobs.append(blob)
        offset += len(blob)
    header = {
        "schema": schema or frame_schema_id(),
        "generation": int(generation),
        "cursor": int(cursor),
        "t0": float(t0),
        "dt": float(dt),
        "version": int(version),
        "columns": [item.descriptor() for item in described],
    }
    header_bytes = json.dumps(
        header, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return (
        FRAME_MAGIC
        + _HEADER_LEN.pack(len(header_bytes))
        + header_bytes
        + b"".join(blobs)
    )


def decode_frame(data: bytes) -> Frame:
    """解码 Frame v1 wire；损坏的字节抛 ValueError，绝不返回半截数据。"""
    if len(data) < 8 or data[:4] != FRAME_MAGIC:
        raise ValueError("不是 plotkit.frame/v1 数据（magic 不匹配）")
    (header_len,) = _HEADER_LEN.unpack_from(data, 4)
    end = 8 + header_len
    if end > len(data):
        raise ValueError("Frame header 长度越界")
    try:
        header = json.loads(data[8:end].decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"Frame header 不是合法 JSON：{exc}") from exc
    if not isinstance(header, dict):
        raise ValueError("Frame header 顶层必须是对象")
    payload = data[end:]
    columns: list[FrameColumn] = []
    for raw in header.get("columns", []):
        if not isinstance(raw, dict):
            raise ValueError("Frame column 描述必须是对象")
        offset = int(raw.get("offset", 0))
        count = int(raw.get("count", 0))
        byte_length = int(raw.get("byte_length", 0) or 0)
        encoding = str(raw.get("encoding", "f4"))
        if offset < 0 or count < 0:
            raise ValueError("Frame column 的 offset/count 不能为负")
        if offset > len(payload):
            raise ValueError("Frame column 的 offset 超出 payload")
        if byte_length < 0:
            raise ValueError("Frame column 的 byte_length 不能为负")
        if encoding != "json":
            dtype = _ENCODINGS.get(encoding)
            if dtype is None:
                raise ValueError(f"不支持的 encoding {encoding!r}")
            size = int(np.dtype(dtype).itemsize) * count
            if offset + size > len(payload):
                raise ValueError("Frame column 的数据长度与 count 不一致")
            blob = payload[offset : offset + size]
        else:
            if byte_length:
                if offset + byte_length > len(payload):
                    raise ValueError("Frame column 的 JSON byte_length 超出 payload")
                blob = payload[offset : offset + byte_length]
            else:
                blob = payload[offset:]
        values = _decode_values(blob, encoding, count)
        columns.append(
            FrameColumn(
                name=str(raw.get("name", "")),
                values=values,
                unit=str(raw.get("unit", "")),
                role=str(raw.get("role", "auto")),
                dtype=str(raw.get("dtype", "")),
                encoding=encoding,
                offset=offset,
                count=count,
                byte_length=byte_length,
            )
        )
    return Frame(
        schema=str(header.get("schema", "")),
        generation=int(header.get("generation", 0)),
        cursor=int(header.get("cursor", 0)),
        t0=float(header.get("t0", 0.0)),
        dt=float(header.get("dt", 0.0)),
        version=int(header.get("version", 0)),
        columns=tuple(columns),
        payload=payload,
    )


def _encoding_for(dtype: Any) -> str:
    kind = np.dtype(dtype)
    if kind.kind == "f":
        return {2: "f2", 4: "f4", 8: "f8"}.get(kind.itemsize, "f8")
    if kind.kind == "i":
        return {1: "i1", 2: "i2", 4: "i4", 8: "i8"}.get(kind.itemsize, "i8")
    if kind.kind == "u":
        return {1: "u1", 2: "u2", 4: "u4", 8: "u8"}.get(kind.itemsize, "u8")
    return "f8"


def encode_frame_from_store(
    store: Any,
    names: Sequence[str],
    *,
    generation: int = 0,
    cursor: int = 0,
    t0: float = 0.0,
    dt: float = 0.0,
    version: int = 0,
) -> bytes:
    """从 DataStore 取列并编码；``store`` 只需提供 values(name) / meta(name)。"""
    columns: list[FrameColumn] = []
    for name in names:
        values = np.asarray(store.values(name))
        meta: Mapping[str, Any] = store.meta(name) or {}
        encoding = _encoding_for(values.dtype)
        columns.append(
            FrameColumn(
                name=name,
                values=tuple(values.ravel().tolist()),
                unit=str(meta.get("unit", "")),
                role=str(meta.get("role", "auto")),
                dtype=str(values.dtype),
                encoding=encoding,
            )
        )
    return encode_frame(
        columns,
        generation=generation,
        cursor=cursor,
        t0=t0,
        dt=dt,
        version=version,
    )


def frame_golden_vector() -> bytes:
    """固定的 golden vector：encode/decode 往返与逐字节稳定性都用它回归。"""
    return encode_frame(
        (
            FrameColumn(
                name="t",
                values=(0.0, 0.5, 1.0),
                unit="s",
                role="x",
                dtype="float32",
                encoding="f4",
            ),
            FrameColumn(
                name="v_out",
                values=(1.0, 2.0, 3.0),
                unit="V",
                role="y",
                dtype="float32",
                encoding="f4",
            ),
        ),
        generation=1,
        cursor=3,
        t0=0.0,
        dt=0.5,
        version=1,
    )
