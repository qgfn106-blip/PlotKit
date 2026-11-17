# -*- coding: utf-8 -*-
"""WP-4 渲染分层基准的输入契约与分布字段。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import bench_layers  # noqa: E402

BASELINE = ROOT / "docs" / "bench_layers_baseline.json"


def test_rendering_baseline_has_distribution_rows() -> None:
    assert BASELINE.is_file()
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert baseline["schema_bench"] == "plotkit-bench-layers/1"
    assert baseline["config"]["unknowns"] == [100, 500, 1000, 5000]
    assert len(baseline["results"]) == 8
    for row in baseline["results"]:
        timing = row["timing"]
        assert {"p50", "p95", "min", "max", "n", "samples", "mean", "stdev"} <= set(timing)
        assert timing["n"] == baseline["config"]["steps"]
        assert {"tracemalloc_peak_mb", "rss_before_mb", "rss_after_mb"} <= set(row["memory"])


def test_rendering_layer_reports_points_and_cases() -> None:
    rows = bench_layers.bench_rendering(100, steps=2, warmup=1)
    assert [row["case"] for row in rows] == ["rendering_rebuild", "rendering_reuse"]
    for row in rows:
        assert row["layer"] == "rendering"
        assert row["points"] == 100
        assert row["channels"] == 6
        assert row["timing"]["p50"] > 0


def test_rendering_fingerprint_change_is_incomparable(tmp_path: Path) -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    baseline["environment_bench"]["processor"] = "different-cpu"
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps(baseline, ensure_ascii=False), encoding="utf-8")
    args = type("Args", (), {"unknowns": [100], "points": None, "steps": 1, "warmup": 0})()
    result, _ = bench_layers.run(args)
    status, details = bench_layers._check(result, baseline)
    assert status == "INCOMPARABLE"
    assert any("processor" in item for item in details)
