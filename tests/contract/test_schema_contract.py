"""P0 冻结契约：schema 加载、哈希与分层隔离。"""

from __future__ import annotations

import subprocess
import sys

import pytest

from plotkit.schema import (
    SCHEMA_DIR,
    SCHEMA_IDS,
    capability_rows,
    contract_hashes,
    load,
    schema_versions,
)

FROZEN_FILES = {
    "figure.v1.json",
    "frame.v1.json",
    "capability.v1.json",
    "compat_matrix.json",
}


def test_load_returns_expected_contract_ids() -> None:
    """四个冻结文件都能按文件名加载，且 $id/schema 正确。"""
    assert load("figure.v1.json")["$id"] == SCHEMA_IDS["figure"]
    assert load("frame.v1.json")["$id"] == SCHEMA_IDS["frame"]
    assert load("capability.v1.json")["$id"] == SCHEMA_IDS["capability"]
    assert load("compat_matrix.json")["schema"] == SCHEMA_IDS["compat"]


def test_load_accepts_short_aliases() -> None:
    """短别名映射回同一批 allowlist 文件。"""
    assert load("figure")["$id"] == SCHEMA_IDS["figure"]
    assert load("frame.v1")["$id"] == SCHEMA_IDS["frame"]
    assert load("capability")["$id"] == SCHEMA_IDS["capability"]
    assert load("compat")["schema"] == SCHEMA_IDS["compat"]


def test_contract_hashes_are_stable_and_cover_frozen_files() -> None:
    """哈希可重复，且四个冻结文件始终在结果中。"""
    first = contract_hashes()
    second = contract_hashes()
    assert first == second
    assert set(first) >= FROZEN_FILES
    assert all(isinstance(value, str) and len(value) == 64 for value in first.values())


def test_schema_import_does_not_pull_upper_layers() -> None:
    """L0 导入不得触发 plotkit 根包的反向依赖。"""
    schema_file = SCHEMA_DIR / "__init__.py"
    code = "\n".join(
        [
            "import importlib.util",
            "import sys",
            "import types",
            "from pathlib import Path",
            "schema_file = Path(sys.argv[1])",
            "pkg = types.ModuleType('plotkit')",
            "pkg.__path__ = [str(schema_file.parent.parent)]",
            "sys.modules['plotkit'] = pkg",
            "spec = importlib.util.spec_from_file_location(",
            "    'plotkit.schema', schema_file",
            ")",
            "module = importlib.util.module_from_spec(spec)",
            "sys.modules['plotkit.schema'] = module",
            "spec.loader.exec_module(module)",
            "names = (",
            "    'plotkit.server', 'plotkit.backends', " "'plotkit.document'",
            ")",
            "for name in names:",
            "    assert name not in sys.modules, name",
            "print('isolated')",
        ]
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(schema_file)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "isolated" in result.stdout


def test_compat_matrix_api_version_and_schema_versions() -> None:
    """兼容矩阵冻结 api_version=1，且版本表与 SCHEMA_IDS 一致。"""
    matrix = load("compat_matrix.json")
    assert matrix["api_version"] == "1"
    assert matrix["schema_versions"] == {
        "figure": [SCHEMA_IDS["figure"]],
        "frame": [SCHEMA_IDS["frame"]],
        "capability": [SCHEMA_IDS["capability"]],
    }


def test_schema_versions_helper() -> None:
    """schema_versions() 读取兼容矩阵并返回版本表。"""
    versions = schema_versions()
    assert versions == load("compat_matrix.json")["schema_versions"]
    assert all(isinstance(value, list) for value in versions.values())


def test_unknown_load_raises_key_error() -> None:
    """allowlist 之外的名字必须报 KeyError。"""
    with pytest.raises(KeyError):
        load("nope")


def test_capability_rows_are_list_of_dicts() -> None:
    """矩阵缺失时返回空表，存在时返回行列表。"""
    rows = capability_rows()
    assert isinstance(rows, list)
    assert len(rows) in (0, 8)
    assert all(isinstance(row, dict) for row in rows)
