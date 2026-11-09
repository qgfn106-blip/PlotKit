"""L0 契约层：只读地暴露 P0 冻结的 JSON 契约。

该模块只允许依赖标准库，且不得 import 任何 ``plotkit.*`` 上层模块；
宿主、渲染后端和文档层都通过这里读取同一份冻结文件。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_DIR = Path(__file__).resolve().parent

SCHEMA_IDS: dict[str, str] = {
    "figure": "plotkit.figure/v1",
    "frame": "plotkit.frame/v1",
    "capability": "plotkit.capability/v1",
    "compat": "plotkit.compat/v1",
}

_CONTRACT_FILES: tuple[str, ...] = (
    "figure.v1.json",
    "frame.v1.json",
    "capability.v1.json",
    "compat_matrix.json",
)

# 别名只映射到上面四个冻结文件，不接受任意路径。
_ALIASES: dict[str, str] = {
    "figure": "figure.v1.json",
    "figure.v1": "figure.v1.json",
    "frame": "frame.v1.json",
    "frame.v1": "frame.v1.json",
    "capability": "capability.v1.json",
    "capability.v1": "capability.v1.json",
    "compat": "compat_matrix.json",
    "compat_matrix": "compat_matrix.json",
}

__all__ = [
    "SCHEMA_DIR",
    "SCHEMA_IDS",
    "load",
    "contract_hashes",
    "schema_versions",
    "capability_rows",
]


def _resolve(name: str) -> str:
    """把公开名称解析为白名单中的文件名。"""
    if name in _CONTRACT_FILES:
        return name
    if name in _ALIASES:
        return _ALIASES[name]
    allowed = ", ".join(_CONTRACT_FILES)
    raise KeyError(f"未知契约文件 {name!r}；可用：{allowed}")


def load(name: str) -> dict:
    """按 UTF-8 读取一个冻结契约文件并返回 ``dict``。"""
    path = SCHEMA_DIR / _resolve(name)
    return json.loads(path.read_text(encoding="utf-8"))


def contract_hashes() -> dict[str, str]:
    """返回 SCHEMA_DIR 中所有 JSON 文件原始字节的 sha256。"""
    result: dict[str, str] = {}
    for path in sorted(SCHEMA_DIR.glob("*.json"), key=lambda item: item.name):
        if path.is_file():
            result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def schema_versions() -> dict[str, list[str]]:
    """从兼容矩阵读取各契约族支持的 schema id。"""
    matrix = load("compat_matrix.json")
    versions: dict[str, list[str]] = matrix["schema_versions"]
    return {key: list(value) for key, value in versions.items()}


def capability_rows() -> list[dict]:
    """读取能力矩阵；该文件由其他切片后续生成，缺失时返回空列表。"""
    path = SCHEMA_DIR / "capability_matrix.json"
    if not path.is_file():
        return []
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows", [])
    return [dict(row) for row in rows] if isinstance(rows, list) else []
