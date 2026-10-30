"""P13-06：动画（figure.anim → 逐帧渲染 → GIF；前端按帧播放）。"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image

import plotkit as pk
from plotkit.backends import mpl_backend


def _fig(frames: int = 8) -> pk.Figure:
    t = np.linspace(0.0, 2.0, 400)
    fig = pk.figure(size=(4.0, 2.6), theme="netlab-dark")
    fig.add_data("t", t, unit="s", role="coord")
    fig.add_data("v", np.sin(6.0 * t), unit="V", role="series")
    fig.add_plot("line", x="t", y="v", label="v")
    fig.set_anim(frames=frames, fps=12)
    return fig


def test_frame_times_span_the_axis():
    fig = _fig(5)
    times = fig.frame_times()
    assert len(times) == 5
    assert times[0] == pytest.approx(0.0)
    assert times[-1] == pytest.approx(2.0)
    assert times == sorted(times)


def test_anim_defaults_come_from_data_range():
    fig = _fig(6)
    anim = fig.anim_settings()
    assert anim["frames"] == 6 and anim["fps"] == 12
    assert anim["t_start"] == pytest.approx(0.0)
    assert anim["t_end"] == pytest.approx(2.0)


def test_animate_gif_has_expected_frames():
    fig = _fig(6)
    payload = fig.animate_gif(width=320, height=200)
    assert payload[:6] in (b"GIF87a", b"GIF89a")
    img = Image.open(io.BytesIO(payload))
    assert img.n_frames == 6
    assert img.size == (320, 200)


def test_animate_frames_differ():
    """每帧的 t 不同，画面必须真的在动。"""
    fig = _fig(4)
    frames = fig.render_frames(width=240, height=160)
    assert len(frames) == 4
    assert len({f for f in frames}) >= 3, "至少三帧内容不同"


def test_animate_respects_t_range():
    fig = _fig(4)
    fig.set_anim(frames=4, t_start=0.5, t_end=1.0)
    assert fig.frame_times() == pytest.approx([0.5, 0.6667, 0.8333, 1.0], abs=1e-3)


def test_anim_endpoint_serves_gif():
    from fastapi.testclient import TestClient

    from plotkit.server.app import create_app

    client = TestClient(create_app(_fig(5)))
    res = client.get("/api/anim", params={"w": 260, "h": 170})
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/gif"
    assert Image.open(io.BytesIO(res.content)).n_frames == 5
    assert client.get("/api/anim", params={"w": 260, "h": 170}).headers["x-plotkit-render"] == "hit"


def test_anim_spec_roundtrip():
    import json

    fig = _fig(5)
    fig.set_anim(frames=5, fps=20, t_start=0.1, t_end=0.9)
    first = fig.to_json()
    assert pk.Figure(spec=json.loads(first)).to_json() == first
    assert "anim" in first


def test_anim_rejects_bad_frames():
    fig = _fig(4)
    with pytest.raises(ValueError):
        fig.set_anim(frames=0)
