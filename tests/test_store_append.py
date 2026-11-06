"""DataStore 追加：几何增长缓冲区不能改变原有语义。"""

from __future__ import annotations

import numpy as np
import pytest

import plotkit as pk


def test_many_pushes_keep_order_and_length():
    store = pk.DataStore()
    store.add("y", np.zeros(0), role="series")
    for i in range(500):
        store.push("y", np.full(10, float(i)))
    data = store.get("y")
    assert data.values.size == 5000
    assert data.meta.length == 5000
    assert data.meta.version == 501  # add 记 1 次，push 500 次
    assert data.values[:10].tolist() == [0.0] * 10
    assert data.values[-10:].tolist() == [499.0] * 10


def test_values_view_tracks_growth():
    store = pk.DataStore()
    store.add("y", np.arange(3, dtype=float), role="series")
    first = store.get("y").values
    assert first.size == 3
    for _ in range(500):
        store.push("y", np.array([1.0, 2.0]))
    assert first.size == 3  # 旧视图长度不漂移
    assert store.get("y").values.size == 1003


def test_append_supports_2d_rows():
    store = pk.DataStore()
    store.add("m", np.zeros((0, 2)), role="series")
    for i in range(300):
        store.push("m", np.array([[float(i), float(-i)]]))
    data = store.get("m")
    assert data.values.shape == (300, 2)
    assert data.values[299].tolist() == [299.0, -299.0]


def test_shape_mismatch_still_raises():
    store = pk.DataStore()
    store.add("y", np.zeros(4), role="series")
    with pytest.raises(ValueError):
        store.push("y", np.zeros((2, 2)))


def test_replace_life_does_not_accumulate():
    store = pk.DataStore()
    store.add("y", np.zeros(5), role="series", life="replace")
    for i in range(50):
        store.push("y", np.full(5, float(i)))
    data = store.get("y")
    assert data.values.size == 5
    assert data.values.tolist() == [49.0] * 5


def test_nbytes_counts_reserved_capacity():
    store = pk.DataStore()
    store.add("y", np.zeros(1000), role="series")
    for _ in range(50):
        store.push("y", np.ones(1000))
    data = store.get("y")
    assert store.nbytes() >= data.values.nbytes  # 含预留容量的实际占用
    assert data.capacity_bytes >= data.values.nbytes
    # 预留不至于失控：不超过逻辑长度 2 倍
    assert data.capacity_bytes <= data.values.nbytes * 2 + 64


def test_push_on_unknown_name_creates_dataset():
    store = pk.DataStore()
    store.push("fresh", np.arange(4.0))
    assert store.get("fresh").values.size == 4


def test_trim_keeps_tail_and_life():
    """环形窗口：trim 只裁旧数据，不能把 append 语义改成 replace。"""
    store = pk.DataStore()
    store.add("t", np.arange(10, dtype=float), role="coord", life="append")
    store.push("t", np.arange(10, 20, dtype=float))
    assert len(store.get("t")) == 20

    store.trim("t", 5)
    assert len(store.get("t")) == 5
    assert list(store.get("t").values) == [15.0, 16.0, 17.0, 18.0, 19.0]
    assert store.get("t").meta.life == "append"

    # 关键：裁过之后还能继续追加（旧实现会退化成"只剩最后一帧"）
    store.push("t", np.array([20.0, 21.0]))
    assert list(store.get("t").values) == [15.0, 16.0, 17.0, 18.0, 19.0, 20.0, 21.0]


def test_trim_noop_when_short():
    store = pk.DataStore()
    store.add("y", np.arange(3, dtype=float), role="series", life="append")
    store.trim("y", 100)
    assert len(store.get("y")) == 3
