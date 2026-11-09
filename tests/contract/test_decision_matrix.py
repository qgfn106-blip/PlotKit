"""能力矩阵 → decision_report() 的逐行一致性（P0 契约冻结）。"""

from __future__ import annotations

from plotkit.backends.selector import capability_rows, decision_report


def test_decision_report_tracks_matrix_order_and_backends():
    rows = capability_rows()
    report = decision_report()
    assert len(rows) == 8
    assert len(report) == 8
    assert [entry["id"] for entry in report] == [row["id"] for row in rows]
    for row, entry in zip(rows, report):
        assert entry["decision"]["backend"] == row["backend"]
        assert isinstance(entry["acceptance"], str) and entry["acceptance"].strip()
        assert entry["decision"]["degraded"] is False
        assert entry["situation"] == row["situation"]
        assert entry["doc_features"]
        assert set(("kind", "fmt", "quality")) <= set(entry["target"])


def test_decision_report_has_no_degradation_when_extras_available():
    report = decision_report()
    assert all(entry["decision"]["degraded"] is False for entry in report)
    assert all(entry["decision"]["backend"] for entry in report)


def test_degraded_report_is_observable():
    rows = capability_rows()
    degraded = decision_report(available={"three": False, "ns": False})
    assert len(degraded) == len(rows) == 8
    needs_extra = [
        row["id"] for row in rows if row.get("match", {}).get("requires_extra")
    ]
    observed = [
        entry["id"] for entry in degraded if entry["decision"]["degraded"] is True
    ]
    assert set(needs_extra) <= set(observed)
    for entry in degraded:
        if entry["decision"]["degraded"]:
            assert entry["decision"]["fallback"]
            assert entry["decision"]["backend"]
