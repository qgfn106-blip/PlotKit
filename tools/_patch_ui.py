"""一次性补丁：把布局持久化 / 撤销重做 / 菜单栏 / 快捷键模块拼进 app.js。"""
from __future__ import annotations

import pathlib

BLOCK = r'''
/* ---------------- 布局（.layout.json）：面板宽 / 折叠 / 展开 / 分组 ----------------
 * 归属规则：spec 决定"图长什么样"，layout 决定"软件怎么摆"（D14）。
 */
function applyLayout(layout) {
  state.layout = Object.assign({ panelWidth: 380, sections: {}, expanded: [], groups: [] }, layout || {});
  if (!Array.isArray(state.layout.groups)) state.layout.groups = [];
  if (!Array.isArray(state.layout.expanded)) state.layout.expanded = [];
  state.expanded = new Set(state.layout.expanded);
  applyPanelWidth(state.layout.panelWidth || 380);
  Object.entries(state.layout.sections || {}).forEach(([id, open]) => {
    const el = $(id);
    if (el && el.tagName === "DETAILS") el.open = Boolean(open);
  });
}

function syncLayoutExpanded() {
  state.layout.expanded = Array.from(state.expanded);
  scheduleLayoutSave();
}

function scheduleLayoutSave() {
  clearTimeout(state.layoutTimer);
  state.layoutTimer = setTimeout(saveLayoutNow, 400);
}

async function saveLayoutNow() {
  const width = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--panel-w")) || 380;
  state.layout.panelWidth = Math.round(width);
  const sections = {};
  document.querySelectorAll("#panel > details[id]").forEach((el) => { sections[el.id] = el.open; });
  state.layout.sections = sections;
  state.layout.expanded = Array.from(state.expanded);
  try {
    await api("/api/layout", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(state.layout),
    });
  } catch (err) {
    setStatus(`布局未保存：${err.message}`, "bad");
  }
}

/* ---------------- 撤销 / 重做 ---------------- */
async function restoreSnapshot(snapshot, reason) {
  state.spec = JSON.parse(snapshot);
  state.committed = snapshot;
  renderLayoutControls();
  renderDatasets();
  renderLayers();
  renderInsets();
  await commit(reason, { record: false });
}

async function undo() {
  if (!state.undo.length) { setStatus("没有可撤销的操作", "bad"); return; }
  state.redo.push(state.committed);
  await restoreSnapshot(state.undo.pop(), "撤销");
}

async function redo() {
  if (!state.redo.length) { setStatus("没有可重做的操作", "bad"); return; }
  state.undo.push(state.committed);
  await restoreSnapshot(state.redo.pop(), "重做");
}

/* ---------------- 菜单栏（结构参照 netlab：紧凑、可键盘操作） ---------------- */
const MENUS = {
  file: {
    title: "文件",
    items: [
      { id: "save-spec", label: "保存 spec.json", kbd: "Ctrl+S", run: () => downloadText("spec.json", JSON.stringify(state.spec, null, 2)) },
      { id: "png", label: "导出 PNG（matplotlib）", kbd: "Ctrl+E", run: () => exportPng() },
      { sep: true },
      { id: "reload", label: "重新载入服务端 spec", run: () => location.reload() },
    ],
  },
  edit: {
    title: "编辑",
    items: [
      { id: "undo", label: "撤销", kbd: "Ctrl+Z", run: () => undo() },
      { id: "redo", label: "重做", kbd: "Ctrl+Y", run: () => redo() },
      { sep: true },
      { id: "dup", label: "复制选中图层", kbd: "Ctrl+D", run: () => duplicateSelected() },
      { id: "del", label: "删除选中图层", kbd: "Delete", run: () => deleteSelected() },
    ],
  },
  insert: {
    title: "插入",
    items: [
      { id: "layer", label: "新建图层", run: () => addLayer() },
      { id: "group", label: "新建分组", run: () => createGroup() },
      { id: "inset", label: "在子图 0 加内嵌图", run: () => addInset() },
    ],
  },
  view: {
    title: "视图",
    items: [
      { id: "panel", label: "收起/展开右侧面板", run: () => $("btn-panel").click() },
      { id: "theme", label: "切换深浅色", run: () => $("btn-theme").click() },
      { sep: true },
      { id: "sections", label: "展开全部面板分组", run: () => setAllSections(true) },
      { id: "collapse", label: "收起数据集/内嵌图", run: () => setAllSections(false) },
    ],
  },
};

let openPop = null;

function renderMenus() {
  const bar = $("menubar");
  bar.innerHTML = "";
  Object.entries(MENUS).forEach(([id, menu]) => {
    const btn = document.createElement("button");
    btn.className = "menu";
    btn.textContent = menu.title;
    btn.dataset.menu = id;
    btn.onclick = (ev) => {
      ev.stopPropagation();
      if (openPop && openPop.dataset.menu === id) { closeMenus(); return; }
      const rect = btn.getBoundingClientRect();
      openMenuAt(id, rect.left, rect.bottom + 4);
    };
    bar.appendChild(btn);
  });
}

function openMenuAt(id, x, y) {
  closeMenus();
  const menu = MENUS[id];
  if (!menu) return;
  const pop = document.createElement("div");
  pop.className = "menu-pop";
  pop.dataset.menu = id;
  menu.items.forEach((item) => {
    if (item.sep) {
      const sep = document.createElement("div");
      sep.className = "sep";
      pop.appendChild(sep);
      return;
    }
    const btn = document.createElement("button");
    btn.innerHTML = `<span>${item.label}</span>${item.kbd ? `<span class="kbd">${item.kbd}</span>` : ""}`;
    btn.onclick = (ev) => {
      ev.stopPropagation();
      closeMenus();
      try { item.run(); } catch (err) { setStatus(`操作失败：${err.message}`, "bad"); }
    };
    pop.appendChild(btn);
  });
  pop.style.left = `${Math.min(x, window.innerWidth - 220)}px`;
  pop.style.top = `${Math.min(y, window.innerHeight - 24 - menu.items.length * 30)}px`;
  document.body.appendChild(pop);
  openPop = pop;
  document.querySelectorAll(".menubar .menu").forEach((b) => b.classList.toggle("open", b.dataset.menu === id));
}

function closeMenus() {
  if (openPop) { openPop.remove(); openPop = null; }
  document.querySelectorAll(".menubar .menu").forEach((b) => b.classList.remove("open"));
}

function setAllSections(open) {
  document.querySelectorAll("#panel > details").forEach((el) => {
    el.open = open && (el.id !== "insetgroup" || !el.hidden);
  });
  scheduleLayoutSave();
}

function downloadText(name, text) {
  const blob = new Blob([text], { type: "application/json;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function duplicateSelected() {
  const layer = state.spec.layers.find((l) => l.id === state.selectedLayer);
  if (!layer) { setStatus("先点一个图层选中它", "bad"); return; }
  const copy = JSON.parse(JSON.stringify(layer));
  copy.id = `l${Math.random().toString(16).slice(2, 10)}`;
  const at = state.spec.layers.indexOf(layer);
  state.spec.layers.splice(at + 1, 0, copy);
  state.selectedLayer = copy.id;
  commit("复制图层");
}

function deleteSelected() {
  const idx = state.spec.layers.findIndex((l) => l.id === state.selectedLayer);
  if (idx < 0) { setStatus("先点一个图层选中它", "bad"); return; }
  state.spec.layers.splice(idx, 1);
  state.selectedLayer = null;
  commit("删图层");
}

function createGroup() {
  const name = prompt("分组名", `分组 ${(state.layout.groups || []).length + 1}`);
  if (!name) return;
  state.layout.groups.push({ id: `g${Date.now().toString(16)}`, name, open: true, layerIds: [] });
  renderLayers();
  scheduleLayoutSave();
  setStatus(`已建分组「${name}」，把图层拖到分组标题上即可归组`, "good");
}

function addInset() {
  const spec = state.spec;
  spec.figure.insets = spec.figure.insets || [];
  const nextSlot = spec.layers.length ? Math.max(...spec.layers.map((l) => l.subplot)) + 1 : 1;
  spec.figure.subplots = Math.max(spec.figure.subplots || 1, nextSlot + 1);
  spec.figure.insets.push({
    id: `i${Math.random().toString(16).slice(2, 8)}`,
    subplot: nextSlot,
    parent: 0,
    rect: [0.62, 0.62, 0.34, 0.32],
    view: {},
    fonts: {},
  });
  commit("加内嵌图");
}

function addLayer() {
  const series = datasetsByRole("series")[0] || datasetsByRole("auto")[0] || state.catalog.datasets[0];
  const coord = datasetsByRole("coord")[0] || state.catalog.datasets[0];
  if (!series || !coord) { setStatus("没有可用数据集，先在 Python 侧 add_data()", "bad"); return; }
  state.spec.layers.push({
    id: `l${Math.random().toString(16).slice(2, 10)}`,
    kind: "line",
    subplot: 0,
    data: { x: coord.name, y: series.name },
    label: null,
    legend: true,
    style: { color: null, width: 1.6, dash: "solid", mode: "lines", opacity: 1.0, marker: { symbol: "circle", size: 7 } },
    view: {},
    annotations: [],
  });
  commit("新建图层");
}

async function exportPng() {
  const res = await fetch("/api/png");
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "plot.png";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/* ---------------- 快捷键 ---------------- */
function bindShortcuts() {
  window.addEventListener("keydown", (ev) => {
    const key = ev.key.toLowerCase();
    const mod = ev.ctrlKey || ev.metaKey;
    if (ev.key === "Escape") { closeMenus(); return; }
    if (mod && key === "z") { ev.preventDefault(); if (ev.shiftKey) redo(); else undo(); return; }
    if (mod && key === "y") { ev.preventDefault(); redo(); return; }
    if (mod && key === "d") { ev.preventDefault(); duplicateSelected(); return; }
    if (mod && key === "s") { ev.preventDefault(); downloadText("spec.json", JSON.stringify(state.spec, null, 2)); return; }
    if (mod && key === "e") { ev.preventDefault(); exportPng().catch((e) => setStatus(`导出失败：${e.message}`, "bad")); return; }
    if ((ev.key === "Delete" || ev.key === "Backspace") && !/input|textarea|select/i.test(document.activeElement.tagName)) {
      ev.preventDefault();
      deleteSelected();
    }
  });
}

document.addEventListener("click", () => closeMenus());
document.addEventListener("click", (ev) => {
  if (ev.target.closest("#panel > details")) setTimeout(scheduleLayoutSave, 0);
}, true);
'''

path = pathlib.Path("src/plotkit/static/app.js")
s = path.read_text(encoding="utf-8")
assert "function renderMenus" not in s, "已经打过补丁"
marker = "startPolling(500);\n\nboot();"
assert marker in s
s = s.replace(
    marker,
    BLOCK + "\nstartPolling(500);\n\nrenderMenus();\nbindShortcuts();\nboot();",
)
path.write_text(s, encoding="utf-8")
print("patched")
