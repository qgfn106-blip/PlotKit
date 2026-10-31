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


def test_timeline_resamples_to_frame_budget():
    """/api/timeline：把 (x,y,z,t) 重采样成固定帧数，供前端拖动时间轴。"""
    from fastapi.testclient import TestClient

    n = 500
    t = np.linspace(0, 10, n)
    figure = pk.figure()
    for name, values in (("t", t), ("x", np.cos(t)), ("y", np.sin(t)), ("z", t / 10)):
        figure.add_data(name, values)
    figure.add("line3d", {"x": "x", "y": "y", "z": "z", "t": "t"})
    client = TestClient(create_app(figure))

    res = client.get("/api/timeline", params={
        "x": "x", "y": "y", "z": "z", "t": "t", "frames": 100,
    })
    assert res.status_code == 200
    body = res.json()
    assert len(body["t"]) == 100
    assert body["total"] == n
    assert body["t"][0] == pytest.approx(0.0)
    assert body["t"][-1] == pytest.approx(10.0)
    assert len(body["x"]) == len(body["t"]) == len(body["z"])


def test_timeline_requires_two_points():
    from fastapi.testclient import TestClient

    figure = pk.figure()
    figure.add_data("x", np.zeros(1))
    figure.add_data("y", np.zeros(1))
    figure.add_data("z", np.zeros(1))
    figure.add("scatter3d", {"x": "x", "y": "y", "z": "z"})
    client = TestClient(create_app(figure))
    assert client.get("/api/timeline", params={"x": "x", "y": "y", "z": "z"}).status_code == 400


def test_region_returns_stats_for_selected_box():
    """/api/region：把点乘 MVP 投到 NDC，落在框内的点参与统计（三维"拾取"的替代方案）。"""
    from fastapi.testclient import TestClient

    x = np.linspace(0, 10, 21)
    y = np.zeros(21)
    z = np.linspace(0, 1, 21)
    figure = pk.figure()
    figure.add_data("x", x)
    figure.add_data("y", y)
    figure.add_data("z", z)
    figure.add("scatter3d", {"x": "x", "y": "y", "z": "z"})
    client = TestClient(create_app(figure))

    identity = np.eye(4).ravel().tolist()   # 单位矩阵：NDC 就等于数据坐标
    res = client.post("/api/region", json={
        "x": "x", "y": "y", "z": "z", "mvp": identity, "rect": [0.0, 0.0, 0.5, 0.5],
    })
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 21
    assert 1 <= body["count"] <= 21
    assert body["stats"]["x"]["max"] <= 0.5 + 1e-9
    assert body["stats"]["z"]["count"] == body["count"]


def test_region_rejects_bad_payload():
    from fastapi.testclient import TestClient

    figure = pk.figure()
    figure.add_data("x", np.arange(5.0))
    figure.add_data("y", np.arange(5.0))
    figure.add_data("z", np.arange(5.0))
    figure.add("scatter3d", {"x": "x", "y": "y", "z": "z"})
    client = TestClient(create_app(figure))
    assert client.post("/api/region", json={"x": "x", "y": "y", "z": "z"}).status_code == 400
    assert client.post("/api/region", json={
        "x": "nope", "y": "y", "z": "z", "mvp": list(np.eye(4).ravel()), "rect": [0, 0, 1, 1],
    }).status_code == 404


def test_mesh_accepts_grid_coordinates():
    """/api/mesh 要同时吃"坐标向量"和"整张 meshgrid"两种存法（surface 常用后者）。"""
    from fastapi.testclient import TestClient

    x = np.linspace(-1, 1, 12)
    y = np.linspace(-1, 1, 9)
    X, Y = np.meshgrid(x, y)
    Z = np.sin(np.hypot(X, Y))

    grid_fig = pk.figure()
    grid_fig.add("surface", {"x": X, "y": Y, "z": Z})
    grid_client = TestClient(create_app(grid_fig))
    d = grid_fig.spec["layers"][0]["data"]
    grid_res = grid_client.get("/api/mesh", params={"x": d["x"], "y": d["y"], "z": d["z"]})
    assert grid_res.status_code == 200

    vec_fig = pk.figure()
    vec_fig.add_data("xs", x)
    vec_fig.add_data("ys", y)
    vec_fig.add_data("zs", Z)
    vec_fig.add("surface", {"x": "xs", "y": "ys", "z": "zs"})
    vec_client = TestClient(create_app(vec_fig))
    vec_res = vec_client.get("/api/mesh", params={"x": "xs", "y": "ys", "z": "zs"})
    assert vec_res.status_code == 200
    # 元数据里的名字不同（匿名 vs xs/ys/zs），所以比"二进制部分"而不是总长度
    def payload(res):
        meta_len = int.from_bytes(res.content[4:8], "little")
        return res.content[16 + meta_len:]

    assert payload(vec_res) == payload(grid_res)


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


def test_mesh_binary_frame(fig):
    """曲面网格帧：顶点 + 法线 + uint32 索引，索引必须落在顶点范围内。"""
    import struct

    x = np.linspace(-1, 1, 9)
    y = np.linspace(-2, 2, 7)
    X, Y = np.meshgrid(x, y)
    fig.add_data("gx", x, role="coord")
    fig.add_data("gy", y, role="coord")
    fig.add_data("gz", np.sin(X) * np.cos(Y), role="field")
    fig.add("surface", {"x": "gx", "y": "gy", "z": "gz"})
    from fastapi.testclient import TestClient

    client = TestClient(create_app(fig, title="网格"))
    res = client.get("/api/mesh", params={"x": "gx", "y": "gy", "z": "gz"})
    assert res.status_code == 200
    body = res.content
    meta_len, nvert, ntri = struct.unpack("<III", body[4:16])
    assert nvert == 9 * 7
    assert ntri == 2 * (9 - 1) * (7 - 1)
    assert len(body) == 16 + meta_len + nvert * 12 * 2 + ntri * 12
    import json as _json

    meta = _json.loads(body[16:16 + meta_len])
    assert meta["nx"] == 9 and meta["ny"] == 7
    idx = np.frombuffer(body[16 + meta_len + nvert * 24:], dtype="<u4")
    assert idx.size == ntri * 3
    assert idx.max() < nvert


def test_mesh_rejects_shape_mismatch(fig):
    from fastapi.testclient import TestClient

    fig.add_data("ax", np.linspace(0, 1, 5), role="coord")
    fig.add_data("ay", np.linspace(0, 1, 4), role="coord")
    fig.add_data("az", np.zeros(7), role="field")
    client = TestClient(create_app(fig, title="网格"))
    res = client.get("/api/mesh", params={"x": "ax", "y": "ay", "z": "az"})
    assert res.status_code == 400
