"""抽稀：min-max 包络（保尖峰）与 LTTB（视觉相似）。

为什么不用等距 `[::step]`：仿真信号里单点尖峰（开关瞬间、运放饱和）会被整段跳过，
图上看起来像"没发生"。包络每个像素列至少保留最小与最大两个点。
"""

from __future__ import annotations

from typing import Tuple

import numpy as np


def minmax_envelope(
    x: np.ndarray,
    y: np.ndarray,
    pixels: int,
    *,
    per_pixel: float = 2.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """把 (x, y) 降采样到像素列数 × per_pixel 个点，保每列 min/max。

    - `pixels`：目标像素列数（前端把画布宽度传进来）；
    - `per_pixel`：每列平均点数，2.0 即"每列保留 min 与 max"；
    - 首尾点始终保留，保证线不"缩进去"。
    """
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    if x.size != y.size:
        raise ValueError(f"x/y 长度不一致: {x.size} vs {y.size}")
    n = x.size
    if n == 0:
        return x, y
    max_points = max(3, int(max(1, pixels) * max(1.0, per_pixel)))
    if n <= max_points:
        return x, y

    bins = max(1, max_points // 2)
    edges = np.linspace(0, n, bins + 1).astype(int)
    keep: list[int] = [0]
    finite = np.isfinite(y)
    for start, stop in zip(edges[:-1], edges[1:]):
        if stop <= start:
            continue
        chunk = y[start:stop]
        mask = finite[start:stop]
        if not mask.any():
            keep.append(start)
            continue
        idx = np.flatnonzero(mask)
        local_min = start + int(idx[np.argmin(chunk[mask])])
        local_max = start + int(idx[np.argmax(chunk[mask])])
        for candidate in sorted({local_min, local_max}):
            if candidate != keep[-1]:
                keep.append(candidate)
    if keep[-1] != n - 1:
        keep.append(n - 1)
    index = np.asarray(keep, dtype=int)
    return x[index], y[index]


def lttb(x: np.ndarray, y: np.ndarray, threshold: int) -> Tuple[np.ndarray, np.ndarray]:
    """Largest-Triangle-Three-Buckets：视觉相似优先的降采样（备选方案）。"""
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    n = x.size
    if x.size != y.size:
        raise ValueError(f"x/y 长度不一致: {x.size} vs {y.size}")
    if threshold >= n or threshold < 3:
        return x, y

    every = (n - 2) / (threshold - 2)
    sampled = [0]
    a = 0
    for i in range(threshold - 2):
        start = int(np.floor((i + 1) * every)) + 1
        stop = int(np.floor((i + 2) * every)) + 1
        stop = min(stop, n)
        if start >= stop:
            start = min(start, n - 1)
            stop = start + 1
        avg_x = float(np.mean(x[start:stop]))
        avg_y = float(np.mean(y[start:stop]))
        range_start = int(np.floor(i * every)) + 1
        range_stop = int(np.floor((i + 1) * every)) + 1
        range_stop = min(range_stop, n)
        candidates = np.arange(range_start, max(range_start + 1, range_stop))
        area = np.abs(
            (x[a] - avg_x) * (y[candidates] - y[a])
            - (x[a] - x[candidates]) * (avg_y - y[a])
        )
        a = int(candidates[int(np.argmax(area))])
        sampled.append(a)
    sampled.append(n - 1)
    index = np.unique(np.asarray(sampled, dtype=int))
    return x[index], y[index]
