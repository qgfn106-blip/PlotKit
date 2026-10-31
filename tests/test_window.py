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


def _assert_window(limits, lo, hi, margin=0.06):
    """mpl 的 xlim 带 5% autoscale 边距，所以只校验"数据区间被完整包含且没跑远"。"""
    got_lo, got_hi = limits["xlim"]
    span = hi - lo
    assert got_lo <= lo + 1e-9 and got_hi >= hi - 1e-9
    assert got_lo >= lo - margin * span and got_hi <= hi + margin * span


def test_window_keeps_only_recent_part():
    fig, _ = _figure(window=2.0)
    _, limits = fig.render(width=400, height=250, with_limits=True)
    _assert_window(limits, 8.0, 10.0)


def test_window_with_replay_cursor():
    fig, _ = _figure(window=2.0)
    _, limits = fig.render(width=400, height=250, t_end=5.0, with_limits=True)
    _assert_window(limits, 3.0, 5.0)


def test_window_clamped_to_data_start():
    fig, _ = _figure(window=5.0)
    _, limits = fig.render(width=400, height=250, t_end=1.0, with_limits=True)
    _assert_window(limits, 0.0, 1.0)


def test_no_window_returns_everything():
    fig, _ = _figure(window=None)
    _, limits = fig.render(width=400, height=250, with_limits=True)
    _assert_window(limits, 0.0, 10.0)


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


def test_render_endpoint_accepts_replay_cursor():
    """回放游标走 /api/render 的 t 参数（figure.json 已随 plotly 退役删除）。"""
    fig, _ = _figure(window=2.0)
    client = TestClient(create_app(fig))
    live = client.get("/api/render?w=300&h=200")
    past = client.get("/api/render?w=300&h=200&t=5")
    assert live.status_code == 200 and past.status_code == 200
    live_lo, live_hi = [float(v) for v in live.headers["x-plotkit-xlim"].strip("[]").split(",")]
    past_lo, past_hi = [float(v) for v in past.headers["x-plotkit-xlim"].strip("[]").split(",")]
    assert live_lo <= 8.0 + 1e-9 and live_hi >= 10.0 - 1e-9
    assert past_lo <= 3.0 + 1e-9 and past_hi >= 5.0 - 1e-9


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
