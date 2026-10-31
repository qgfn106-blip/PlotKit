"""三维动画 API（D39）：复用 Plotter、逐帧改位姿、GIF/MP4 导出。"""

from __future__ import annotations

import numpy as np
import pytest

pk = pytest.importorskip("plotkit")
pv = pytest.importorskip("pyvista")


def _figure():
    x = np.linspace(-2, 2, 12)
    y = np.linspace(-2, 2, 12)
    X, Y = np.meshgrid(x, y)
    Z = np.sin(np.hypot(X, Y))
    fig = pk.figure(size=(4, 3), dpi=80)
    fig.add("surface", {"x": X, "y": Y, "z": Z})
    fig.set_view(0, elev=22, azim=-58)
    return fig


def _poses(n=6):
    t = np.linspace(0, 2 * np.pi, n)
    return np.stack([1.2 * np.cos(t), 1.2 * np.sin(t), 1.0 + 0.2 * np.sin(2 * t)], axis=1)


def test_frames_are_png_and_count_matches():
    fig = _figure()
    anim = fig.anim3d(frames=5, fps=10, width=240, height=180)
    anim.add_box("car", size=(0.4, 0.3, 0.2))
    frames = anim.frames_png()
    assert len(frames) == 5
    assert all(f[:8] == b"\x89PNG\r\n\x1a\n" for f in frames)


def test_motion_changes_pixels():
    fig = _figure()
    anim = fig.anim3d(frames=6, fps=10, width=240, height=180)
    car = anim.add_box("car", size=(0.5, 0.35, 0.25))
    anim.set_pose(car, _poses(6), heading=np.linspace(0, 2 * np.pi, 6))
    frames = anim.frames_png()
    # 注意 _poses 走整圈，首末帧位姿相同，所以比较中间帧
    assert frames[0] != frames[len(frames) // 2], "位姿变了，画面必须跟着变"


def test_trail_grows_over_frames():
    fig = _figure()
    anim = fig.anim3d(frames=4, fps=10, width=240, height=180)
    anim.add_trail("path", _poses(20), color="#94a3b8")
    frames = anim.frames_png()
    assert len(frames) == 4
    assert frames[0] != frames[-1]


def test_gif_bytes_have_magic():
    fig = _figure()
    anim = fig.anim3d(frames=4, fps=8, width=200, height=150)
    car = anim.add_box("car", size=(0.4, 0.3, 0.2))
    anim.set_pose(car, _poses(4))
    payload = anim.save_gif()
    assert payload[:6] in (b"GIF87a", b"GIF89a")
    assert len(payload) > 2000


def test_radian_heading_is_converted():
    fig = _figure()
    anim = fig.anim3d(frames=2, fps=8, width=160, height=120)
    car = anim.add_box("car")
    anim.set_pose(car, np.zeros((2, 3)), heading=[0.0, np.pi / 2])
    assert car.headings is not None
    assert car.headings[1] == pytest.approx(90.0, abs=1e-6)


def test_invalid_frame_count_rejected():
    fig = _figure()
    with pytest.raises(ValueError):
        fig.anim3d(frames=0)
    with pytest.raises(ValueError):
        fig.anim3d(frames=10, fps=0)


def test_mp4_without_ffmpeg_raises(monkeypatch):
    fig = _figure()
    anim = fig.anim3d(frames=2, fps=8, width=160, height=120)
    anim.add_box("car")
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(RuntimeError, match="ffmpeg"):
        anim.save_mp4("unused.mp4")


def test_unknown_actor_name_raises():
    fig = _figure()
    anim = fig.anim3d(frames=2, fps=8, width=160, height=120)
    with pytest.raises(KeyError):
        anim.set_pose("nope", np.zeros((2, 3)))
