# 画布自由布局、图层面板独立窗口与批注（2026-11-03）

- 状态：P1–P5 全部实现（2026-11-03，3.16.10）
- 来源：用户在 netlab 里使用 PlotKit 的反馈（2026-11-03，原话见下）
- 关联：`PlotKit/docs/REQUIREMENTS_AND_PROGRESS.md`（PK-R17…PK-R20）、`NetlabHome/netlab/docs/PROGRESS.md` §7.49

## 用户原话（不改写）

> plotkit即使有了netlab预计算数据后依然无法播放，并且移动拖拽表格画布感觉不太合理，拖拽后难回到合理尺寸，并且持续窗口播放被打断
>
> 图层设置希望是独立窗口，类似于netlab里的独立窗口
>
> 并且画布与子图现在功能不完善，没法方便做到自行拖拽子图到合适区域，即子图能够相互重叠
>
> 以及不能自行放置文字框，数据标注，箭头等类似于笔记功能

参考产品（用户只给链接，未说明用途）：[veusz](https://github.com/veusz/veusz)、[ParaView](https://github.com/Kitware/ParaView)。

## P1 预计算后无法播放（已修复）

**现象**：netlab 预计算完成、PlotKit 也拿到了数据，点播放没反应。

**根因（实测，不是推测）**：`PlotKit/src/plotkit/backends/series.py` 的 `time_bounds()` 只遍历 `spec.layers` 的 `x` 数据算时间范围；而 netlab 按 D-PlotView 只登记数据集、**不自动建图层**，于是：

- `/api/meta` 返回 `time: {min: null, max: null, count: 600}`；
- 前端 `playStep()`（`PlotKit/src/plotkit/static/app.js:1230-1235`）在 `min==null` 时返回 0，播放游标不动。

**修复**：`time_bounds()` 在图层范围为空时回退到 `role="coord"` 数据集（`_coord_time_bounds`）。

**回归**：
- `PlotKit/tests/test_window.py::test_time_bounds_falls_back_to_coord_data_without_layers`（先红后绿）
- `NetlabHome/netlab/tests/test_plotkit_channels.py::test_plotkit_meta_has_time_range_after_precompute`（预计算后 `/plotkit/api/meta` 的 time 必须有 min/max/count）
- 实测：预计算 1 s → `meta = {'min': 0.0005, 'max': 1.0, 'count': 600}`；netlab 全量 414 passed。

## P2 拖拽尺寸与"播放被打断"（已实现）

- 面板拖宽时不再逐帧 `scheduleRender`（重绘会占住 `state.busy`，`tickPlay` 在 busy 时跳过推进，表现为一拖就断播）；松手后只重绘一次。
- 「布局」分组新增 **复位面板宽度** 按钮（等价于原来隐藏的双击 grip）。

## P3 图层面板独立窗口（已实现，2026-11-03，方案 A）

现状（改前）：图层设置是 PlotKit 页内右侧 `aside#panel`，窄宿主里会被挤。

三种落法与最终选择：

| 方案 | 做法 | 代价 |
| --- | --- | --- |
| **A 页内浮动面板（已选）** | 面板可拖出成浮动卡，拖标题栏移动、拖右下角缩放 | 最小，跨宿主一致（浏览器 / netlab 内嵌 / pywebview 都可用） |
| B 独立浏览器窗口 | `window.open('/plotkit/?panel=1')` + `BroadcastChannel` 同步 spec | 需要跨窗口同步协议与回环，留作 A 之上再加的"弹出"按钮 |
| C 桌面子窗口 | pywebview 新窗口 | 依赖宿主，Web 端没有 |

实现：

- 「布局」分组加 `#btn-layer-pop`（图层独立窗口 / 图层已浮出 开关）；
- 浮窗 `#layerWin`（`position:absolute` 于 `.plotwrap`）含标题栏 `#layerWinBar`、`#layerWinBody`、右下 `.layerwin-resize`、`#btn-layer-close`（收起）；
- 浮出 = 把 `#layerSect`（图层 `<details>` 整块）搬进 `#layerWinBody`；收起 = 插回 `#panel` 内嵌图分组之前。DOM 不重建，`renderLayers()` 照旧按 id 写入，事件绑在卡片上不失效；
- 拖动/缩放用 pointer 事件，`clampLayerWinRect()` 把窗口夹在画布内，最小 260×180；
- 位置/尺寸/浮出状态存 `localStorage["pk.layerWin"] = {popped, rect}`，刷新后还原；**只有 `popped:true` 才还原**，收起后刷新不会自己弹出来；
- 点标题栏上的按钮不算拖窗（`ev.target.closest("button")` 直接返回）。

实测（无头 Edge + CDP，2026-11-03 14:44，15 项断言全 PASS）：

- 初始图层分组在 `#panel`，浮窗隐藏；点「图层独立窗口」→ 可见、分组搬进 `#layerWinBody`、面板里查不到 `#layerSect`；
- 初始 rect 380×418；拖标题栏 −120/+80 → 位置同步变化并写入 localStorage；
- 拖右下角 +70/+50 → 380×418 → 450×468；
- 点「收起」→ 隐藏、分组回到 `#panel`、`localStorage` 里 `popped:false`；刷新后仍是收起；
- 再浮出后刷新 → 还原浮出，rect 还原为 450×468。

测试：`PlotKit/tests/test_layer_window.py` 5 项静态护栏（结构 id、pop/dock 的 DOM 搬运、拖动/缩放的 clamp 与按钮排除、持久化与还原条件、CSS 存在）。用 P4 备份的旧静态文件对照，8 个关键标记全部缺失，确认这些断言在改前是红的。

## P4 子图自由布局、可重叠（已实现，2026-11-03）

现状（改前）：`figure.subplots` 是整数，`ncols × nrows` 网格，图层按 `slot` 索引落格（`PlotKit/src/plotkit/spec/model.py:88,217`）。

实现决策：**不动 `figure.subplots` 的整数语义**，新增可选 `figure.layout = [{slot, rect:[x,y,w,h]}]`（rect 为 figure 比例 0–1，y 从下往上）。理由：整数网格是老 spec 的既有契约，几十处测试与 netlab 桥接都按它走；把自由位置拆成独立可选字段，`layout` 缺失时渲染路径与改前逐字节一致，回归风险最低。

规则：

- `layout` 里出现 `slot` 时该槽位用 `add_axes(rect)` 摆位，允许互相重叠；未写进 `layout` 的槽位退回网格位置；
- `figure.subplots` 会自动抬到 `max(layout slot)+1`，保证槽位都有 axes；
- 自由布局时关掉 constrained_layout（`set_layout_engine("none")`），否则它会重排 `add_axes`；
- 重叠 z 序：`layout` 数组顺序，后面的在上；
- 校验（`spec/validate.py`）：必须是数组、`slot` 为非负整数且不重复、`rect` 必须 4 个数且 `w/h>0`、坐标限制 `-0.5…1.5`（出血容差）。

UI：

- 「布局」分组加 `#btn-free-layout`（自由布局）/ `#btn-grid-layout`（回到网格）；
- 开启时用服务端 `X-PlotKit-Axes` 给的包围盒 materialize 初始 rect，否则按网格算；
- 画布上 `#layout-overlay` 里每个槽一个虚线框，拖动移动、右下把手缩放，松手 `commit("拖拽子图"/"缩放子图")`，坐标三位小数；
- 关键坑：前端 canvas 渲染路径不写 `state.img`，自由布局必须强制走服务端渲染（`redraw()` 里 `clientRenderable(spec) && !layoutList().length`），否则拖拽框拿不到几何、永远不显示。

实测（无头 Edge + CDP，2026-11-03 14:10）：

- 点「自由布局」→ `layout=[{slot:0,rect:[0.09385,0.124,0.4248,0.752]},{slot:1,rect:[0.53635,0.124,0.4248,0.752]}]`，overlay 可见、2 个 `.layout-box`；
- 拖 40px/20px → rect `[0.208,0.042,0.425,0.752]` 且 PUT `/api/spec` 持久化；
- 把槽 0 拖到槽 1 上 → 两 rect 完全相同（重叠成立），画面只剩一个虚线框「槽 0」，两个图层都还在；
- 点「回到网格」→ `layout=null`、overlay 隐藏、0 个框、`plotImg.naturalWidth>0`（恢复前端渲染）。

测试：`PlotKit/tests/test_free_layout.py` 11 项（`PYTHONPATH=src python -m pytest tests/test_free_layout.py -q`）：重叠摆位、无 layout 时网格不变、缺项退回网格、6 组非法 rect/slot 校验、服务端渲染回报 boxes、静态页控件存在。用旧 vendored 代码跑同一测试为 8 failed，确认能红。

## P5 批注：文字框 / 数据标注 / 箭头（已实现）

现状：spec 已有图层级 `annotations`（`hline`/`vline`/`band`/`text`）与图级 `figure.shapes`（`line`/`rect`/`arrow`/`triangle`/`path`），但前端没有编辑入口，也没有"笔记"这一层语义。

目标（已落地）：

- 新增可选 `figure.notes`，条目 `{id, kind, text, color, size, …}`，`kind` ∈ `text` / `arrow` / `region` / `mark`：
  - `text`：`pos=[x, y]`，figure 比例坐标（左下原点），渲染成带圆角底色的文字框；
  - `arrow`：`start=[x, y]` → `end=[x, y]`，figure 比例坐标，末端可带文字；
  - `region`：`rect=[x, y, w, h]`，figure 比例坐标的虚线框（圈重点）；
  - `mark`：`subplot` + `x`/`y`（**数据坐标**），服务端用 `ax.annotate` 画引线文字，缩放/平移后仍指向同一个数据点；前端另存 `pos` 仅用于覆盖层定位。
- 前端工具条：文字框 / 箭头 / 框选 / 数据标注 / 删除批注；点工具后在画布上点击或拖拽即建；拖动批注移动，双击改文字，`Delete` 删除，`Esc` 退出工具。
- 批注存在时强制走服务端渲染（前端 canvas 路径不写 `state.img`，覆盖层拿不到几何）；与 inset / 子图拖拽共用 `clamp01` 与 pointer 事件套路。

实现位置：

- `PlotKit/src/plotkit/spec/model.py`：`NOTE_TYPES` + `new_note()`；
- `PlotKit/src/plotkit/spec/validate.py`：`KNOWN_FIGURE_KEYS` 加 `notes`，逐条校验 kind / 坐标 / rect / size / subplot；
- `PlotKit/src/plotkit/backends/mpl_backend.py`：`_draw_notes()`（figure 比例用 `fig.text` / `FancyArrowPatch` / `Rectangle`，数据标注用 `ax.annotate`），在 `_draw_decorations()` 之后调用；
- `PlotKit/src/plotkit/api/native.py`：`update_layout` 白名单加 `notes`；
- `PlotKit/src/plotkit/static/{index.html,app.js,app.css}`：`#note-overlay` 覆盖层 + 工具条 + `renderNoteOverlay()` / `addNote()` / `bindNoteOverlay()`。

实测（无头 Edge + CDP，临时脚本已删）：

- 文字框、箭头、框选、数据标注依次创建成功，`figure.notes` 依次为 `text` → `+arrow` → `+region` → `+mark`；数据标注落在 `x=1.4349, y=2.5064`（数据坐标）；
- `GET /api/spec` 返回 4 条批注（已持久化）；
- 双击文字框改为「改过的批注」，`figure.notes[0].text` 同步；
- 选中第一条点「删除批注」→ 剩 `arrow/region/mark` 三条；
- 截图确认框选虚线框、箭头、数据标注引线、文字框都画进了 PNG。

测试：`PlotKit/tests/test_notes.py` 14 项（`PYTHONPATH=src python -m pytest tests/test_notes.py -q`）：默认值/未知类型、合法 spec、7 组非法条目（未知 kind、缺坐标、零宽 rect、3 元 rect、mark 缺 y、size=0）、notes 非数组、渲染像素确实变化、mark 指向不存在子图不崩、服务端 PUT→render 往返、静态页控件存在。改前端前该文件的静态护栏断言是红的（`note-overlay` 不存在）。

## 不做

- 不做完整矢量编辑器（Veusz / ParaView 那种工程级标注系统）；只做"笔记级"批注。
- 批注暂不支持富文本、旋转、多选批量拖动。

## 验收

- P1：预计算后 `/api/meta` 有 time 范围；播放游标能前进；回归测试红→绿。
- P2：拖面板宽度时播放不断；复位按钮一次点回默认宽度。
- P4：见上「实测」，`test_free_layout.py` 11 项绿；能红已用旧 vendored 代码验证。
- P3：见上「实测」，`test_layer_window.py` 5 项绿；能红已用 P4 备份的旧静态文件验证（8 个标记全缺）。
- P5：见上「实测」，`test_notes.py` 14 项绿；静态护栏在改前端前为红；CDP 冒烟 4 类批注全部建/改/删成功并持久化。

