"""CLI `render3d`（接缝 3）：把 frames.json 发给服务并存成 zip。"""

from __future__ import annotations

import io
import json
import zipfile

import numpy as np
from fastapi.testclient import TestClient

import plotkit as pk
from plotkit import cli
from plotkit.server.app import create_app


def _client():
    fig = pk.figure()
    x = np.linspace(0, 1, 12)
    fig.add_data("x", x)
    fig.add_data("y", np.cos(x * 4))
    fig.add_plot("line", x="x", y="y")
    return TestClient(create_app(fig)), fig


def test_post_batch_returns_zip_bytes():
    api, fig = _client()
    data = cli.post_batch(api, {"width": 160, "height": 120,
                                "frames": [{"spec": fig.spec}]})
    with zipfile.ZipFile(io.BytesIO(data)) as bundle:
        assert bundle.namelist() == ["frame_0001.png"]


def test_post_batch_raises_on_error():
    api, _ = _client()
    try:
        cli.post_batch(api, {"frames": []})
    except RuntimeError as exc:
        assert "批量渲染失败" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("空 frames 应当抛错")


def test_render3d_command_writes_zip(tmp_path, monkeypatch):
    api, fig = _client()
    payload_path = tmp_path / "frames.json"
    payload_path.write_text(json.dumps({"width": 160, "height": 120,
                                        "frames": [{"spec": fig.spec}]}), encoding="utf-8")
    out = tmp_path / "out.zip"

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def post(self, path, json=None):  # noqa: A002
            return api.post(path, json=json)

    import httpx

    monkeypatch.setattr(httpx, "Client", _FakeClient)
    code = cli.main(["render3d", "--payload", str(payload_path), "--out", str(out)])
    assert code == 0
    assert out.exists()
    with zipfile.ZipFile(out) as bundle:
        assert bundle.namelist() == ["frame_0001.png"]


def test_render3d_is_registered():
    parser = cli.build_parser()
    args = parser.parse_args(["render3d", "--payload", "x.json"])
    assert args.func is cli._cmd_render3d
