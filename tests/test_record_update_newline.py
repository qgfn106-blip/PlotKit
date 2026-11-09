from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "record_update.py"
    spec = importlib.util.spec_from_file_location("record_update_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_write_preserving_newlines_keeps_crlf(tmp_path):
    module = _load_module()
    target = tmp_path / "README.md"
    target.write_bytes(b"a\r\nb\r\n")
    module._write_preserving_newlines(target, "a\nb\nc\n")
    assert target.read_bytes() == b"a\r\nb\r\nc\r\n"


def test_write_preserving_newlines_keeps_lf(tmp_path):
    module = _load_module()
    target = tmp_path / "README.md"
    target.write_bytes(b"a\nb\n")
    module._write_preserving_newlines(target, "a\nb\nc\n")
    assert target.read_bytes() == b"a\nb\nc\n"
