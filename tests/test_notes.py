"""PK-R21 画布批注：`figure.notes` 的文字框 / 箭头 / 框选区域 / 数据标注。

约定：
- text   : pos=[x, y]，figure 比例坐标（左下原点）；
- arrow  : start=[x, y] → end=[x, y]，figure 比例坐标，可带 text；
- region : rect=[x, y, w, h]，figure 比例坐标虚线框；
- mark   : subplot + x/y（数据坐标），画在数据点上并带引线文字。
"""

from __future__ import annotations

import pytest

import plotkit as pk
from plotkit.backends import mpl_backend
from plotkit.spec.model import new_note
from plotkit.spec.validate import validate_spec


def _figure(**kwargs):
    fig = pk.figure(ncols=1, subplots=1, **kwargs)
    fig.add_plot(x=[0, 1, 2], y=[1, 2, 3], subplot=0)
    return fig


def _codes(report) -> set[str]:
    return {issue.code for issue in report.errors}


def _render(fig) -> bytes:
    return mpl_backend.render_bytes(fig.spec, fig.store, width=480, height=300, dpi=80)


def test_new_note_defaults_and_unknown_kind() -> None:
    note = new_note("text", pos=[0.2, 0.3], text="hi")
    assert note["kind"] == "text"
    assert note["id"].startswith("n")
    assert note["text"] == "hi"
    with pytest.raises(ValueError):
        new_note("sticky")


def test_notes_validate_ok() -> None:
    fig = _figure()
    fig.spec["figure"]["notes"] = [
        {"kind": "text", "pos": [0.1, 0.9], "text": "整体说明"},
        {"kind": "arrow", "start": [0.2, 0.2], "end": [0.4, 0.4], "text": "趋势"},
        {"kind": "region", "rect": [0.5, 0.5, 0.3, 0.2], "text": "重点"},
        {"kind": "mark", "subplot": 0, "x": 1.0, "y": 2.0, "text": "峰值"},
    ]
    assert validate_spec(fig.spec).ok


@pytest.mark.parametrize(
    ("note", "code"),
    [
        ({"kind": "sticky", "pos": [0.1, 0.1]}, "figure.notes.kind"),
        ({"kind": "text"}, "figure.notes.point"),
        ({"kind": "arrow", "start": [0.1, 0.1]}, "figure.notes.point"),
        ({"kind": "region", "rect": [0.1, 0.1, 0.0, 0.2]}, "figure.notes.rect"),
        ({"kind": "region", "rect": [0.1, 0.1, 0.2]}, "figure.notes.rect"),
        ({"kind": "mark", "subplot": 0, "x": 1.0}, "figure.notes.point"),
        ({"kind": "text", "pos": [0.1, 0.1], "size": 0}, "figure.notes.size"),
    ],
)
def test_notes_validation_rejects_bad_items(note, code) -> None:
    fig = _figure()
    fig.spec["figure"]["notes"] = [note]
    report = validate_spec(fig.spec)
    assert code in _codes(report)


def test_notes_must_be_list() -> None:
    fig = _figure()
    fig.spec["figure"]["notes"] = {"kind": "text"}
    assert "figure.notes" in _codes(validate_spec(fig.spec))


def test_notes_change_rendered_pixels() -> None:
    fig = _figure()
    baseline = _render(fig)
    fig.spec["figure"]["notes"] = [
        {"kind": "text", "pos": [0.12, 0.92], "text": "文字框", "color": "#b91c1c"},
        {"kind": "arrow", "start": [0.55, 0.55], "end": [0.7, 0.65], "text": "箭头"},
        {"kind": "region", "rect": [0.3, 0.2, 0.35, 0.3], "text": "区域"},
        {"kind": "mark", "subplot": 0, "x": 1.0, "y": 2.0, "text": "数据点"},
    ]
    with_notes = _render(fig)
    assert with_notes != baseline


def test_mark_on_missing_subplot_is_skipped() -> None:
    fig = _figure()
    fig.spec["figure"]["notes"] = [{"kind": "mark", "subplot": 9, "x": 0.0, "y": 0.0}]
    assert _render(fig)


def test_server_roundtrip_notes() -> None:
    """端到端：PUT 带 notes 的 spec → /api/render 出图，且与无批注图不同。"""
    from fastapi.testclient import TestClient
    from plotkit.server.app import create_app

    fig = _figure()
    client = TestClient(create_app(fig))
    before = client.get("/api/render", params={"w": 480, "h": 300})
    assert before.status_code == 200

    spec = dict(fig.spec)
    spec["figure"] = dict(spec["figure"])
    spec["figure"]["notes"] = [
        {"kind": "text", "pos": [0.15, 0.9], "text": "服务端批注"},
        {"kind": "region", "rect": [0.4, 0.4, 0.3, 0.25]},
    ]
    put = client.put("/api/spec", json=spec)
    assert put.status_code == 200, put.text
    after = client.get("/api/render", params={"w": 480, "h": 300})
    assert after.status_code == 200
    assert after.content != before.content


def test_static_page_exposes_note_controls() -> None:
    from pathlib import Path

    static = Path(__file__).resolve().parents[1] / "src" / "plotkit" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    js = (static / "app.ts").read_text(encoding="utf-8")

    assert 'id="note-overlay"' in html
    assert 'id="btn-note-text"' in html
    assert 'id="btn-note-arrow"' in html
    assert 'id="btn-note-region"' in html
    assert 'id="btn-note-mark"' in html
    assert "function renderNoteOverlay" in js
    assert "function addNote" in js
    assert 'kind: "mark"' in js
    assert "添加批注" in js
