"""图层独立窗口（PK-R19 / P3 方案 A）：页内浮动卡的结构与交互护栏。

纯前端功能，pytest 里只能静态护栏；真实拖拽/收起的验证用无头浏览器做过，
见 docs/specs/2026-11-03-canvas-free-layout-annotations.md 的 P3 实测。
"""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "src" / "plotkit" / "static"
HTML = (STATIC / "index.html").read_text(encoding="utf-8")
JS = (STATIC / "app.js").read_text(encoding="utf-8")
CSS = (STATIC / "app.css").read_text(encoding="utf-8")


def test_layer_section_is_addressable_and_movable():
    # 图层分组必须能整体搬家：面板里是 #layerSect，浮窗里是 #layerWinBody
    assert 'id="layerSect"' in HTML
    assert 'id="layerWinBody"' in HTML
    assert 'id="layerWin"' in HTML
    assert 'id="layerWinBar"' in HTML
    assert 'id="btn-layer-pop"' in HTML
    assert 'id="btn-layer-close"' in HTML


def test_layer_window_moves_dom_and_restores_it():
    assert "function popLayers(" in JS
    assert "function dockLayers(" in JS
    # 浮出：把 #layerSect 塞进浮窗 body；收起：插回 #panel（内嵌图分组之前）
    assert "body.appendChild(sect)" in JS
    assert "panel.insertBefore(sect" in JS
    # 按钮是开关，收起按钮直接收
    assert '$("btn-layer-pop").onclick' in JS
    assert '$("btn-layer-close").onclick' in JS


def test_layer_window_drag_and_resize_are_clamped():
    assert "function applyLayerWinRect(" in JS
    assert "function clampLayerWinRect(" in JS
    assert 'startDrag(ev, "move")' in JS
    assert 'startDrag(ev, "resize")' in JS
    # 拖动标题栏不能把「收起」按钮也当成拖窗
    assert 'ev.target.closest("button")' in JS
    # 缩放下限，别拖成 0 宽
    assert "LAYERWIN_MIN_W" in JS and "LAYERWIN_MIN_H" in JS


def test_layer_window_remembers_state_and_survives_resize():
    assert 'const LAYERWIN_KEY = "pk.layerWin"' in JS
    assert "localStorage.setItem(LAYERWIN_KEY" in JS
    assert "readLayerWinSaved" in JS
    # 只还原「上次是浮出状态」的窗口，收起后刷新不该又弹出来
    assert "saved && saved.popped" in JS
    assert 'window.addEventListener("resize"' in JS


def test_layer_window_styles_exist():
    for sel in (".layerwin", ".layerwin-bar", ".layerwin-body", ".layerwin-resize"):
        assert re.search(re.escape(sel) + r"\b", CSS), sel
    assert ".layerwin[hidden] { display: none; }" in CSS
