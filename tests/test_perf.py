"""构图缓存与压缩：同一份 spec 第二次请求必须命中缓存，改 spec 后必须失效。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import plotkit as pk
from plotkit.server.app import create_app


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    fig = pk.figure()
    fig.add_plot(x=[0, 1, 2], y=[1, 2, 3], label="a")
    return TestClient(create_app(fig, layout_path=tmp_path / "layout.json"))


def test_figure_json_second_call_hits_cache(client: TestClient) -> None:
    first = client.get("/api/figure.json?pixels=800")
    assert first.status_code == 200
    assert first.headers["X-PlotKit-Cache"] == "miss"
    second = client.get("/api/figure.json?pixels=800")
    assert second.headers["X-PlotKit-Cache"] == "hit"
    assert second.json() == first.json()


def test_figure_json_cache_invalidated_by_spec(client: TestClient) -> None:
    client.get("/api/figure.json?pixels=800")
    spec = client.get("/api/spec").json()
    spec["figure"]["title"] = "换个标题"
    assert client.put("/api/spec", json=spec).status_code == 200
    again = client.get("/api/figure.json?pixels=800")
    assert again.headers["X-PlotKit-Cache"] == "miss"
    assert again.json()["layout"]["title"]["text"] == "换个标题"


def test_figure_json_cache_invalidated_by_data(client: TestClient, tmp_path: Path) -> None:
    fig = pk.figure()
    fig.add_data("t", [0.0, 1.0], life="append")
    fig.add_data("v", [1.0, 2.0], life="append")
    fig.add_plot(x="t", y="v")
    app_client = TestClient(create_app(fig, layout_path=tmp_path / "layout.json"))
    assert app_client.get("/api/figure.json?pixels=400").headers["X-PlotKit-Cache"] == "miss"
    assert app_client.get("/api/figure.json?pixels=400").headers["X-PlotKit-Cache"] == "hit"
    fig.store.push("t", [2.0])
    fig.store.push("v", [3.0])
    assert app_client.get("/api/figure.json?pixels=400").headers["X-PlotKit-Cache"] == "miss"
    assert len(app_client.get("/api/figure.json?pixels=400").json()["data"][0]["y"]) == 3
