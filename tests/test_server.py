import json
import struct

import numpy as np
import pytest

import plotkit as pk
from plotkit.server.app import MAGIC, create_app


@pytest.fixture()
def fig():
    figure = pk.figure(title="服务测试")
    figure.add_data("t", np.linspace(0, 1, 11), unit="s", role="coord")
    figure.add_data("v", np.linspace(10, 0, 11), unit="V", role="series", tags=["输出"])
    figure.add_plot("line", x="t", y="v", label="V")
    return figure


@pytest.fixture()
def client(fig):
    from fastapi.testclient import TestClient

    return TestClient(create_app(fig, title="服务测试"))


def test_meta(client):
    payload = client.get("/api/meta").json()
    assert payload["app"] == "PlotKit"
    assert payload["spec_version"] == "0.1"
    assert {"line", "marker", "bar"} <= {k["kind"] for k in payload["kinds"]}


def test_index_page(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "PlotKit" in res.text
    # 2026-10-31 起渲染走 matplotlib（D33），页面不再加载 plotly，改为一张 <img>
    assert "plotly" not in res.text.lower()
    assert 'id="plotImg"' in res.text


def test_static_assets_served_without_plotly(client):
    """plotly bundle 已在 P13-09 删除（D33）；前端资源只剩 app.js/css。"""
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/vendor/plotly-basic.min.js").status_code == 404


def test_get_spec(client, fig):
    payload = client.get("/api/spec").json()
    assert payload["spec_version"] == fig.spec["spec_version"]
    assert payload["layers"][0]["data"] == {"x": "t", "y": "v"}


def test_put_spec_valid_roundtrip(client, fig):
    spec = json.loads(json.dumps(fig.spec))
    spec["figure"]["title"] = "改过的标题"
    res = client.put("/api/spec", json=spec)
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert client.get("/api/spec").json()["figure"]["title"] == "改过的标题"


def test_put_spec_invalid_returns_all_errors(client, fig):
    spec = json.loads(json.dumps(fig.spec))
    spec["layers"][0]["data"]["y"] = "ghost"
    spec["layers"][0]["view"]["xlim"] = [0]
    res = client.put("/api/spec", json=spec)
    assert res.status_code == 400
    body = res.json()
    assert body["ok"] is False
    assert len(body["errors"]) >= 2



def test_datasets_catalog(client):
    payload = client.get("/api/datasets").json()
    names = [d["name"] for d in payload["datasets"]]
    assert "t" in names and "v" in names
    assert "输出" in payload["groups"]


def test_series_binary_roundtrip(client):
    res = client.get("/api/series", params={"x": "t", "y": "v"})
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/octet-stream"
    body = res.content
    assert body[:4] == MAGIC
    meta_len, npoints = struct.unpack("<II", body[4:12])
    meta = json.loads(body[12:12 + meta_len].decode("utf-8"))
    pairs = np.frombuffer(body[12 + meta_len:], dtype="<f4").reshape(-1, 2)
    assert npoints == 11 == pairs.shape[0]
    assert meta["y"] == "v"
    assert pairs[0, 0] == pytest.approx(0.0, abs=1e-6)
    assert pairs[-1, 1] == pytest.approx(0.0, abs=1e-5)


def test_series_downsampled_to_pixels(client):
    client.app  # noqa: B018 - 仅确认 app 可用
    res = client.get("/api/series", params={"x": "t", "y": "v", "pixels": 4})
    body = res.content
    meta_len, npoints = struct.unpack("<II", body[4:12])
    assert npoints <= 11


def test_series_unknown_dataset_is_404(client):
    assert client.get("/api/series", params={"x": "t", "y": "nope"}).status_code == 404


def test_png_endpoint(client):
    res = client.get("/api/png", params={"dpi": 60})
    assert res.status_code == 200
    assert res.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_live_server_start_stop(fig):
    from plotkit.server.live import LiveServer

    server = LiveServer(fig)
    url = server.start()
    try:
        assert url.startswith("http://127.0.0.1:")
        import urllib.request

        with urllib.request.urlopen(url + "api/meta", timeout=5) as resp:
            assert b"PlotKit" in resp.read()
    finally:
        server.stop()


def test_sink_detection_fallback(monkeypatch):
    from plotkit.runtime import sink

    monkeypatch.setattr(sink, "detect_sink", lambda: "browser")
    assert sink.detect_sink() == "browser"


def test_xyz_binary_frame(client, fig):
    """/api/xyz：magic + meta_len + n + json + float32 (x,y,z)，供 WebGL 直接上传。"""
    fig.add_data("z", np.linspace(0, 1, 11))
    res = client.get("/api/xyz", params={"x": "t", "y": "v", "z": "z"})
    assert res.status_code == 200
    body = res.content
    assert body[:4] == MAGIC
    meta_len, n = struct.unpack("<II", body[4:12])
    meta = json.loads(body[12:12 + meta_len])
    assert n == 11 and meta["total"] == 11
    assert len(body) == 12 + meta_len + n * 12
    values = np.frombuffer(body[12 + meta_len:], dtype="<f4").reshape(-1, 3)
    assert np.allclose(values[0], [0.0, 10.0, 0.0], atol=1e-6)
    assert np.allclose(values[-1], [1.0, 0.0, 1.0], atol=1e-6)


def test_xyz_unknown_dataset_is_404(client):
    res = client.get("/api/xyz", params={"x": "nope", "y": "v", "z": "z"})
    assert res.status_code == 404


def test_pick_returns_nearest_data_point(client, fig):
    res = client.get("/api/pick", params={"x": 0.5, "y": 5.0, "sx": 1, "sy": 10})
    assert res.status_code == 200
    data = res.json()
    assert data["hit"] is True
    assert 0 <= data["i"] < 11
    assert abs(data["x"] - 0.5) < 0.06 and abs(data["y"] - 5.0) < 0.6


def test_pick_misses_when_far_away(client, fig):
    data = client.get("/api/pick", params={"x": 99, "y": 99}).json()
    assert data["hit"] is False
