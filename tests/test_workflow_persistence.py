"""端到端工作流：编辑 → PKF1 数据持久化 → 刷新重开 → 真实渲染 → 导出 → 再重开。"""

from __future__ import annotations

import io

import numpy as np
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
Image = pytest.importorskip("PIL.Image")

from fastapi.testclient import TestClient  # noqa: E402
from plotkit.api.native import Figure, figure  # noqa: E402
from plotkit.server.app import create_app  # noqa: E402
from plotkit.spec import io as spec_io  # noqa: E402
from plotkit.spec.model import new_note  # noqa: E402
from plotkit.store.frame import decode_frame, encode_frame_from_store  # noqa: E402


def _new_figure():
    fig = figure(title="Workflow")
    fig.add_data("t", np.linspace(0.0, 1.0, 41), unit="s", role="coord")
    fig.add_data("v", np.linspace(0.0, 1.0, 41), unit="V", role="series")
    fig.add_plot("line", x="t", y="v")
    return fig


def test_edit_persist_refresh_render_export_reopen(tmp_path):
    fig = _new_figure()
    client = TestClient(create_app(fig, layout_path=tmp_path / "layout.json"))

    # 1) 编辑：通过服务端 PUT /api/spec 修改标题并加一条批注。
    spec = client.get("/api/spec").json()
    spec["figure"]["title"] = "Workflow edited"
    spec["figure"]["notes"] = [
        new_note("text", text="edited", pos=(0.05, 0.95), size=10)
    ]
    put = client.put("/api/spec", json=spec)
    assert put.status_code == 200, put.text[:300]
    edited_spec = client.get("/api/spec").json()
    assert edited_spec["figure"]["title"] == "Workflow edited"

    # 2) PKF1 持久化数据 + spec JSON 落盘。
    frame_bytes = encode_frame_from_store(fig.store, ["t", "v"])
    frame_path = tmp_path / "figure.pkf1"
    frame_path.write_bytes(frame_bytes)
    assert frame_path.read_bytes()[:4] == b"PKF1"
    spec_path = tmp_path / "figure.json"
    spec_io.save(edited_spec, spec_path)

    # 3) 刷新：新建 app/client，从磁盘重开 spec 与 PKF1，并重建数据集。
    reopened = Figure.load_spec(spec_path)
    decoded = decode_frame(frame_path.read_bytes())
    for column in decoded.columns:
        reopened.store.add(
            column.name,
            np.asarray(column.values),
            unit=column.unit,
            role=column.role,
        )
    assert reopened.to_spec() == edited_spec
    refreshed = TestClient(create_app(reopened, layout_path=tmp_path / "layout2.json"))
    assert refreshed.get("/").status_code == 200

    # 4) 真实渲染并导出 PNG；导出的文件必须能被独立解码。
    render = refreshed.get(
        "/api/render",
        params={"w": 320, "h": 220, "dpi": 60, "fmt": "png"},
        headers={"Accept-Encoding": "identity"},
    )
    assert render.status_code == 200, render.text[:300]
    assert render.headers["content-type"].startswith("image/png")
    exported = refreshed.get("/api/png")
    assert exported.status_code == 200, exported.text[:300]
    export_path = tmp_path / "export.png"
    export_path.write_bytes(exported.content)
    with Image.open(io.BytesIO(export_path.read_bytes())) as image:
        assert image.size[0] > 100 and image.size[1] > 100
        assert image.convert("RGB").getcolors(maxcolors=10**7)

    # 5) 再次重开导出的 spec，语义与原编辑状态一致。
    resaved = tmp_path / "resaved.json"
    reopened.save_spec(resaved)
    assert Figure.load_spec(resaved).to_spec() == edited_spec
