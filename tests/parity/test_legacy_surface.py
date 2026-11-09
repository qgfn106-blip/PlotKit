"""旧版 HTTP 表面回归：P0 不得改动 /api/meta|spec|layout|render 的既有行为。"""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402
from plotkit.api.native import figure  # noqa: E402
from plotkit.server.app import create_app  # noqa: E402


@pytest.fixture
def legacy(tmp_path):
    fig = figure(title="服务测试")
    fig.add_data("t", np.linspace(0, 1, 11), unit="s", role="coord")
    fig.add_data("v", np.linspace(10, 0, 11), unit="V", role="series")
    fig.add_plot("line", x="t", y="v", label="V")
    layout_path = tmp_path / "layout.json"
    app = create_app(fig, title="服务测试", layout_path=layout_path)
    return TestClient(app), fig, layout_path


def test_get_meta_keeps_legacy_keys(legacy):
    client, _, _ = legacy
    response = client.get("/api/meta")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["app"] == "PlotKit"
    assert {
        "spec_version",
        "title",
        "kinds",
        "themes",
        "datasets",
        "warnings",
        "window",
    } <= set(payload)
    assert {"line", "marker", "bar"} <= {item["kind"] for item in payload["kinds"]}
    assert "netlab-dark" in payload["themes"]


def test_get_spec_keeps_legacy_shape(legacy):
    client, fig, _ = legacy
    response = client.get("/api/spec")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert payload["spec_version"] == fig.spec["spec_version"]
    assert payload["layers"][0]["data"] == {"x": "t", "y": "v"}


def test_put_spec_roundtrip(legacy):
    client, fig, _ = legacy
    response = client.put("/api/spec", json=fig.spec)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["ok"] is True
    assert "warnings" in response.json()
    assert client.get("/api/spec").json()["layers"][0]["data"] == {"x": "t", "y": "v"}


def test_get_put_layout_roundtrip(legacy):
    client, _, layout_path = legacy
    empty = client.get("/api/layout")
    assert empty.status_code == 200
    assert empty.headers["content-type"].startswith("application/json")
    assert empty.json() == {}

    payload = {"panel": "left", "zoom": 2}
    put = client.put("/api/layout", json=payload)
    assert put.status_code == 200
    assert put.headers["content-type"].startswith("application/json")
    assert put.json()["ok"] is True
    assert put.json()["path"] == str(layout_path)

    again = client.get("/api/layout")
    assert again.status_code == 200
    assert again.json() == payload


def test_get_render_keeps_legacy_png(legacy):
    client, _, _ = legacy
    response = client.get("/api/render", params={"w": 240, "h": 160, "dpi": 60})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert len(response.content) > 1000
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
