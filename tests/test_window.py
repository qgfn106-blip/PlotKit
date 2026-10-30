from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

import plotkit as pk
from plotkit.server.app import create_app
from plotkit.spec.validate import validate_spec


def _figure(window=None):
    fig = pk.figure(window=window)
    t = np.linspace(0.0, 10.0, 1001)
    fig.add_data("t", t, unit="s", role="coord", life="append")
    fig.add_data("v", np.sin(t), unit="V", role="series", life="append")
    fig.add_plot(x="t", y="v", label="v")
    return fig, t


def test_window_keeps_only_recent_part():
    fig, t = _figure(window=2.0)
    out = fig.plotly(pixels=400)
    x = [v for v in out["data"][0]["x"] if v is not None]
    assert min(x) >= 8.0 - 1e-9
    assert max(x) == pytest.approx(10.0)
    assert out["layout"]["xaxis"]["range"] == pytest.approx([8.0, 10.0])


def test_window_with_replay_cursor():
    fig, _ = _figure(window=2.0)
    out = fig.plotly(pixels=400, t_end=5.0)
    x = [v for v in out["data"][0]["x"] if v is not None]
    assert min(x) >= 3.0 - 1e-9
    assert max(x) <= 5.0 + 1e-9
    assert out["layout"]["xaxis"]["range"] == pytest.approx([3.0, 5.0])


def test_window_clamped_to_data_start():
    fig, _ = _figure(window=5.0)
    out = fig.plotly(pixels=400, t_end=1.0)
    assert out["layout"]["xaxis"]["range"] == pytest.approx([0.0, 1.0])


def test_no_window_returns_everything():
    fig, _ = _figure(window=None)
    out = fig.plotly(pixels=None)
    assert len(out["data"][0]["x"]) == 1001


def test_window_validation_rejects_negative():
    fig, _ = _figure(window=1.0)
    fig.spec["figure"]["window"] = -3
    report = validate_spec(fig.spec, store=fig.store)
    assert [i.code for i in report.errors] == ["figure.window"]


def test_time_bounds_and_window_helper():
    fig, _ = _figure()
    assert fig.time_bounds() == pytest.approx((0.0, 10.0))
    fig.window(3.0)
    assert fig.spec["figure"]["window"] == 3.0


def test_meta_reports_time_and_api_window():
    fig, _ = _figure(window=2.0)
    client = TestClient(create_app(fig))
    meta = client.get("/api/meta").json()
    assert meta["window"] == 2.0
    assert meta["time"]["min"] == pytest.approx(0.0)
    assert meta["time"]["max"] == pytest.approx(10.0)
    assert meta["time"]["count"] == 1001


def test_figure_json_accepts_replay_cursor():
    fig, _ = _figure(window=2.0)
    client = TestClient(create_app(fig))
    live = client.get("/api/figure.json?pixels=300").json()
    past = client.get("/api/figure.json?pixels=300&t=5").json()
    assert live["layout"]["xaxis"]["range"] == pytest.approx([8.0, 10.0])
    assert past["layout"]["xaxis"]["range"] == pytest.approx([3.0, 5.0])


def test_clear_endpoint_empties_layers_and_data():
    fig, _ = _figure(window=None)
    client = TestClient(create_app(fig))
    res = client.post("/api/clear")
    assert res.status_code == 200 and res.json()["ok"] is True
    spec = client.get("/api/spec").json()
    assert spec["layers"] == []
    names = [d["name"] for d in client.get("/api/datasets").json()["datasets"]]
    assert names == ["t", "v"]
    lengths = [d["length"] for d in client.get("/api/datasets").json()["datasets"]]
    assert lengths == [0, 0]
