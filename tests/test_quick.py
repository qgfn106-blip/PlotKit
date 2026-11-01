"""`pk.quick()`：写代码时的一行出图。"""

from __future__ import annotations

import numpy as np
import pytest

import plotkit as pk

PNG_MAGIC = bytes.fromhex("89504e470d0a1a0a")


def test_quick_returns_png_bytes():
    out = pk.quick(np.sin(np.arange(64) / 5.0))
    assert isinstance(out, bytes) and out[:8] == PNG_MAGIC
    assert len(out) > 2000


def test_quick_accepts_xy_and_writes_file(tmp_path):
    path = tmp_path / "a.png"
    out = pk.quick(np.arange(20.0), np.cos(np.arange(20.0)), path=path)
    assert out == str(path)
    assert path.exists() and path.stat().st_size > 1000


def test_quick_respects_kind_and_style():
    out = pk.quick(np.arange(10.0), kind="marker", color="#ff8800", markersize=4)
    assert out[:8] == PNG_MAGIC


def test_quick_rejects_length_mismatch():
    with pytest.raises(ValueError, match="长度不一致"):
        pk.quick(np.arange(5.0), np.arange(6.0))


def test_quick_rejects_bad_arity():
    with pytest.raises(TypeError):
        pk.quick()


def test_quick_svg(tmp_path):
    path = tmp_path / "a.svg"
    pk.quick(np.arange(12.0), path=path, fmt="svg")
    text = path.read_text(encoding="utf-8")
    assert "<svg" in text and "<path" in text


def test_quick_multi_series():
    t = np.arange(80.0) / 8
    out = pk.quick(t, [np.sin(t), np.cos(t)], labels=["sin", "cos"])
    assert out[:8] == PNG_MAGIC
    assert len(out) > 3000


def test_quick_multi_series_length_mismatch():
    t = np.arange(10.0)
    with pytest.raises(ValueError, match="长度不一致"):
        pk.quick(t, [np.zeros(10), np.zeros(9)])
