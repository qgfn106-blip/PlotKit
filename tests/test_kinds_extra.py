"""P13-07：补齐方法表漏项（stairs / broken_barh / eventplot / bxp / psd / specgram）。"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

import plotkit as pk
from plotkit.backends import mpl_backend


def _colors(payload: bytes) -> int:
    return len(set(Image.open(io.BytesIO(payload)).convert("RGB").getdata()))


def _fig(kind: str, cfg: dict) -> pk.Figure:
    fig = pk.figure(size=(5.0, 3.4), theme="netlab-dark")
    fig.add(kind, cfg)
    return fig


def test_stairs_renders_steps():
    fig = _fig("stairs", {"y": np.array([1.0, 3, 2, 4]), "x": np.arange(5.0)})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert mpl_fig.axes[0].patches or mpl_fig.axes[0].lines
    assert _colors(fig.render(width=420, height=280)) > 16


def test_broken_barh_draws_segments():
    fig = _fig("broken_barh", {"y": np.array([[0.0, 2.0], [4.0, 1.5]]), "x": np.array([1.0])})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    # broken_barh 返回的是 BrokenBarHCollection（挂在 collections 下，不是 patches）
    assert len(mpl_fig.axes[0].collections) == 1
    assert len(mpl_fig.axes[0].collections[0].get_paths()) == 2


def test_eventplot_renders_events():
    rng = np.random.default_rng(2)
    fig = _fig("eventplot", {"x": rng.random(40)})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert mpl_fig.axes[0].collections
    assert _colors(fig.render(width=420, height=280)) > 16


def test_bxp_computes_stats_from_data():
    rng = np.random.default_rng(3)
    fig = _fig("bxp", {"y": rng.normal(size=(2, 60))})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert len(mpl_fig.axes[0].patches) == 2, "两行数据应得到两个箱体"


def test_psd_renders_spectrum():
    t = np.linspace(0, 1, 512)
    fig = _fig("psd", {"x": np.sin(2 * np.pi * 25 * t), "nfft": 128})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert mpl_fig.axes[0].lines
    assert _colors(fig.render(width=420, height=280)) > 16


def test_specgram_renders_image():
    t = np.linspace(0, 1, 512)
    fig = _fig("specgram", {"x": np.sin(2 * np.pi * 40 * t), "nfft": 128})
    mpl_fig = mpl_backend.to_figure(fig.spec, fig.store, dpi=80)
    assert mpl_fig.axes[0].images, "specgram 应产生一张时频图"
    assert _colors(fig.render(width=420, height=280)) > 16


def test_new_kinds_registered():
    from plotkit.backends import registry as reg

    for kind in ("stairs", "broken_barh", "eventplot", "bxp", "psd", "specgram"):
        assert kind in reg.kinds()
        assert reg.resolve(kind).dimension == 2


def test_spec_roundtrip():
    import json

    fig = _fig("stairs", {"y": np.arange(4.0)})
    first = fig.to_json()
    assert pk.Figure(spec=json.loads(first)).to_json() == first
