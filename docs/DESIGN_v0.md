# PlotKit 设计计划 v0（拟定稿，未动代码）

> **历史文档提示（2026-10-31）**：本文是 v0 设计阶段的记录。D33 之后 plotly 后端已整体删除（`backends/plotly_backend.py`、`Figure.plotly()`、`/api/figure.json`），D38 之后新增 PyVista 可选三维后端。当前的唯一口径见 [REQUIREMENTS_AND_PROGRESS.md](REQUIREMENTS_AND_PROGRESS.md)。

> 状态：grilling 收口稿。本文件只描述设计，不含任何实现代码。确认后按 §11 票单开工。
> 日期：2026-10-30　｜　暂名：**PlotKit**（目录 `ProjectPoint/PlotKit/`，包名 `plotkit`，可随时改名）
> 需求来源：用户原话「将得到的数据用 Bokeh 库绘制出来，能否提高效率与运行速度，并且提高交互性能，先拟定计划」→ 经 Q1–Q15 逐轮收口。

---

## 1. 结论（TL;DR）

1. **不用 Bokeh 替换现有画法。** 硬事实：Bokeh 完全没有 3D（18 种图层里 7 种 3D 直接废掉）、核心包 1,393,481 B（gzip 387,085，约为 uPlot 的 27 倍）、任意数据源变更触发 glyph **全量重绘**（无增量路径）。
2. **做一套 spec + 双后端**：`plotly.js` 负责浏览器交互，`matplotlib` 负责静态/论文级导出与浏览器无等价物的兜底（clabel / quiver / streamplot / quiver3d / 3D 光照面）。
3. **新组件独立成包** `ProjectPoint/PlotKit/`，与 `NetlabHome` 平级，单向依赖（PlotKit 绝不 import netlab）。
4. **第一版是垂直切片**：`line / scatter / bar` + 2D 子图网格 + 命名数据注册表 + `spec.json` + 浏览器交互 + 与 netlab 并行新增页签。其余 15 种 kind 与其余 canvas 走老路。
5. **数据通路沿用 HTTP cursor 拉取**（改二进制分片），不引入 WebSocket/SSE。
6. **验收用分段计时瀑布**（仿真 → 采样 → 传输 → 解码 → 建图 → 绘制 → 背压），不是"看起来更快了"。

---

## 2. 决策台账（D 台账）

| 编号 | 决策 | 理由 / 出处 |
|---|---|---|
| D1 | 一套 spec + 双后端（plotly.js 交互 / matplotlib 静态兜底） | Bokeh 无 3D 且体积/全量重绘不可接受（Q2） |
| D2 | 三层分离：**L1 数据** / **L2 呈现 spec** / **L3 视窗**；L2 权威在 Python | 缩放平移永不回后端；语义改动回后端才有唯一真相（Q3） |
| D3 | 数据源注册表 + **延迟绑定**：`add_data(name, arr, tags, unit, role)`，spec 只存名字引用 | 用户设想"只传数据+命名打标签，前端选用法"（Q4） |
| D4 | `spec.json` 是唯一真相，Python codegen 由它**单向**生成，不做反向解析 | 避免双权威（Q4） |
| D5 | 数据集生命周期 `life="append"`（默认，可回看）/ `"replace"`（只保最新 + version 防抖） | 用户"可视化依赖的动态数据可删，计算结果程序自存"（Q5） |
| D6 | 双存储域：程序自存业务数据 / 库只管可视化临时数据；临时 store → 引用计数解绑 → 待回收区（延迟删除，可撤销）→ 会话结束/超配额/手动清理才真删；`export()` / `history()` 做追溯 | 反对 `close()` 即 `os.remove()`（Q6） |
| D7 | 第一版纯 Python，Rust 后置 | 瓶颈在 IO 不在 CPU；接口先钉死（Q8） |
| D8 | 第一版垂直切片：`line/scatter/bar` + 2D 子图 | 先能测"能不能替"，不先重写 1.2 万行（Q9） |
| D9 | 展示 sink 三级自动探测：`inline`（notebook） → `window`（PySide6/QtWebEngine） → `browser`；PySide6 为可选 extra | 用户在 VS Code 里要弹窗口不要跳浏览器 |
| D10 | 回写协议：呈现改动用 **全量 spec 替换**；需要计算的东西用**派生请求 op**（hist 分箱 / corrcoef / 抽稀 / FFT），Python 算完注册成新命名数据集 | 前端永不实现数学（Q10） |
| D11 | PlotKit 独立目录/独立包，三条硬边界（不 import netlab / netlab 不复制其代码 / spec 带版本号） | 用户"独立在新文件夹，不要与现有工程混在一起" |
| D12 | 全新独立包，**借鉴** MultiPlotter 的代码结构但**不 import** | 其 `registries.py` 模块级构建 `DRAW_REGISTRY` 会拖进 matplotlib |
| D13 | 第一版与 netlab **并行新增页签**（开关 `settings.json` + `?chart=plotkit`），验收通过后**删旧**，连开关一起删 | 可 A/B 对拍、随时退回、零回归；用户要求"完成即删旧、不留双轨" |
| D14 | UI 自定义 = 外观级（A：主题/令牌/字体/网格/工具栏）+ 布局级（B：面板停靠、子图槽位拖拽、布局方案保存/恢复） | 用户选 A+B |
| D15 | 验收用分段计时瀑布 + 绝对门槛（§8） | 用户"对比实时计算渲染" |
| D16 | 传输沿用 HTTP cursor 拉取 + ArrayBuffer float32 二进制分片 + `store.push()` 适配器 | 离线友好、零新增协议；WebSocket 留作将来 |

---

## 3. 三层架构与权威归属

| 层 | 内容 | 权威在哪 | 回不回后端 |
|---|---|---|---|
| **L1 数据** | 命名数据集（时间序列、场、表格、图像） | Python `store` | 只读给前端；前端只发"派生请求" |
| **L2 呈现 spec** | 图层（kind / 数据引用 / 样式 / 轴 / 图例 / 子图槽位） | Python `spec` | **回**：前端改完全量回传，Python 校验后成为新权威 |
| **L3 视窗** | 缩放、平移、框选、hover、tooltip 内容 | 浏览器 | **不回**，纯前端状态，不写盘 |

一句话：**spec 决定"图长什么样"，layout/theme 决定"这个软件怎么摆"。** 同一份 spec 换一份 layout 仍是同一张图；换 spec 才是另一张图。

---

## 4. 数据层（L1）

### 4.1 注册 API（延迟绑定）

```python
import plotkit as pk

pk.data.add("t",     t, unit="s", role="coord",  tags=["时间"])
pk.data.add("v_out", v, unit="V", role="series", tags=["信号", "输出"], life="append")
pk.data.add("field", F, role="field", tags=["矢量场"], dim=2)   # 将来 quiver/heatmap

fig = pk.figure(subplots=(2, 1), ncols=1, size=(12.8, 8.4), theme="netlab-dark")
fig.add_plot("line", x="t", y="v_out", subplot=0)   # 只传名字，不传数组
```

- `role ∈ {coord, series, field, table, image}`：决定"能绑到哪种 kind 的哪个参数"，绑定不合法就报错（防止 `x=` 传了个二维场）。
- `tags` 是给人看与检索用的，是**前端下拉列表的分组依据**，也是导出时的注释。
- 数据的**实际字节只传一次**（按内容哈希/版本号），之后 spec 里只出现名字。

### 4.2 生命周期与回收

- `life="append"`：追加，保留全部（可回看历史）；`life="replace"`：只保留最新，前端按 `version` 防抖。
- 临时 store 在系统缓存目录，会话级命名空间；引用计数归零 → 待回收区（清单可见、可撤销）→ 会话结束/超配额/手动清理才真删。
- `pk.data.export("v_out.csv")` / `pk.history("v_out")` 做追溯。

### 4.3 大数据（落盘）

| 项 | 默认值 |
|---|---|
| 内存热窗 | 200 万点 / 60 s（先到为准） |
| 落盘块 | 1,000,000 点 / 块，float32（≈4 MB/块），分文件 + 索引（起止时间、min/max） |
| 会话配额 | 2 GB，超限触发待回收区清理提示 |
| 抽稀 | 请求 = (通道, t0, t1, 像素宽)，目标 ≤2 点/像素列：**min-max 包络**保尖峰（LTTB 作备选） |
| 返回量 | 单帧 ≤ ~2000 点 |
| 缓存 | LRU，命中 <16 ms；缩放/平移首帧 <100 ms |

---

## 5. spec v0 字段模型

```jsonc
{
  "spec_version": "0.1",
  "figure": {
    "size": [12.8, 8.4],        // 英寸
    "dpi": 100,
    "ncols": 1,
    "subplots": 2,               // 槽位总数 = 行×列
    "theme": "netlab-dark",
    "title": "RC 电路瞬态响应",
    "link_x": true               // 共享 x 轴范围（L3 联动，不写回）
  },
  "layers": [
    {
      "id": "l1",                                 // 稳定 id，前端 undo/重排用
      "kind": "line",                             // line | scatter | bar（v0）
      "subplot": 0,
      "data": {"x": "t", "y": "v_out"},           // 只有名字（D3）
      "label": "V_out",
      "legend": true,
      "style": {
        "mode": "lines",                          // lines | markers | lines+markers
        "color": "#4fc3f7",
        "width": 1.6,
        "dash": "solid",
        "marker": {"symbol": "circle", "size": 6, "opacity": 1.0},
        "fill": null                              // null | "tozeroy" | "tonexty"
      },
      "view": {
        "title": null, "xlabel": "t / s", "ylabel": "V / V",
        "xlim": [0, 5], "ylim": null,
        "xscale": "linear", "yscale": "linear",   // 预留 log
        "grid": true, "invert_y": false
      },
      "annotations": []                           // {type: text|hline|vline|band, ...}
    }
  ]
}
```

**校验规则（v0）**
1. `spec_version` 必须存在且可识别；不识别 → 明确报错，不猜。
2. `layers[].data` 的每个键必须在 store 中存在，且 `role` 与 kind 要求匹配（`line.y` 要 `series`，`line.x` 要 `coord`）。
3. `subplot` ∈ `[0, figure.subplots)`；同一槽位的所有 layer 维度必须一致（沿用 MultiPlotter 的"2D/3D 不可混排"规则）。
4. 未知字段**保留并透传**（前向兼容：老版本 PlotKit 读新 spec 不丢信息），校验时记 warning 而不是报错。
5. 前端若发来 `spec_version` 相同但字段类型错误的 spec，整份拒绝并回传 diff 定位，不做"尽力修复"。

---

## 6. 两套编程语法 + 一个 spec

三种入口产生**同一份 spec**，可互相混用（这是"编程时依然能用这个库"的关键）：

```python
# ① 显式 API（原生风格）
fig.add_plot("line", x="t", y="v_out", label="V_out", width=1.6)

# ② matplotlib 风格代理（语法兼容，不引入 matplotlib 依赖）
fig, ax = pk.subplots(2, 1)
ax[0].plot("t", "v_out", label="V_out")          # 只接受名字，纯数组会被自动注册成匿名数据集
ax[0].set_xlabel("t / s")

# ③ plotly 风格代理
fig.add_trace({"type": "scatter", "x": "t", "y": "v_out", "mode": "lines"})
fig.update_layout(title="RC 瞬态")
```

语法兼容的边界（说清楚，避免"假兼容"）：
- **支持**：`plot/scatter/bar/hist/pie/imshow/contour/contourf`、`set_xlim/ylim/xlabel/ylabel/title/xscale/grid/legend`、`subplots/add_subplot/tight_layout`、`savefig`、`show`；plotly 侧 `add_trace/update_layout/update_traces/make_subplots`。
- **不支持**：把 numpy 数组直接塞进 `ax.plot(x, y)` 然后指望它去做 mpl 的自动刻度细节——数组会被自动注册为匿名数据集，行为等价但 spec 里出现的是名字。
- **降级**：mpl 专有参数（`zorder`、`rasterized`、`clip_on`、`hatch`、`path_effects`…）不进入 spec，遇到时**记 warning 并忽略**，而不是静默丢弃。若用户要求"必须一模一样"，用 `fig.savefig()` 走 matplotlib 后端出 PNG。

---

## 7. 后端

| 能力 | plotly.js（交互） | matplotlib（静态/兜底） |
|---|---|---|
| line / scatter / bar / hist / pie / heatmap / image / table | ✅ 原生 | ✅ 原生 |
| contour（含填充叠加） | ✅ `contour` | ✅ `contourf`+`contour` |
| **clabel（等高线内联标注）** | ❌ 无 | ✅ 兜底 PNG |
| **quiver / quiver3d** | ❌ 无真箭头（只能合成 segment 迹） | ✅ 兜底 PNG |
| **streamplot** | ❌ 无 2D 流线 | ✅ 兜底 PNG |
| surface / line3d / scatter3d / bar3d / hist3d / stream3d | ✅（WebGL 真相机，优于 mplot3d 画家算法） | ✅ |
| hist / hist3d 分箱 | 自己实现（Python 侧算 bin，前端只画） | mpl 自带 |

**兜底策略**：一次 figure 里只要出现浏览器无等价物的图层，就整图走 matplotlib 出 PNG/SVG（并在工具栏标注"静态图，交互不可用"），不做"一半交互一半静态"的缝合。

---

## 8. 性能验收（分段计时瀑布）

同一份数据（5000 帧 × 8 通道）、同一台机器、老 canvas 与新 PlotKit 并排：

| 段 | 记什么 | 预算（每帧 16.7 ms） |
|---|---|---|
| ① 仿真计算 | `scene.step(dt)` 单步 | ≤ 8 ms |
| ② 采样/记录 | `probes()` + `recorder.push()` | ≤ 1 ms |
| ③ 序列化/传输 | 字节数 + 往返 | ≤ 2 ms |
| ④ 前端解码/入库 | 解析 + 写入 store | ≤ 2 ms |
| ⑤ spec→图元 | layer 展开 trace | ≤ 1 ms |
| ⑥ 绘制/合成 | canvas 或 WebGL | ≤ 4 ms |
| ⑦ 背压 | 丢帧数、队列深度 | 丢帧 = 0 |

附加绝对门槛：首帧 < 100 ms、缩放/平移一帧 < 50 ms、hover < 16 ms、切页签 < 100 ms、稳态 JS heap < 200 MB、吞吐 ≥ 仿真步速 × 2。

**测量方法**：后端每帧带单调时钟戳；前端 `performance.now()`；开测前 3 次 ping-pong 取最小 RTT/2 校准两钟偏移（不校准则两钟相差数分钟，数据无意义）。每段取 p50/p95。

---

## 9. 前端（页签 / 编辑器 / 布局）

- **容器**：新页签「图表（PlotKit）」，与现有页签并列；图表区用 CSS Grid 承载 `nrows × ncols` 槽位。
- **交互**（v0 必备）：滚轮缩放、拖拽平移、框选、hover 读数、图例点选隐藏、双击复位、导出 PNG、全屏。
- **编辑器**（受控，D2）：右侧属性面板改 spec（数据下拉、kind、颜色/线型、轴范围、标题、图例）；改动 → 全量回传 → Python 校验 → 回显。
- **布局（D14 A+B）**：
  - 外观：主题（浅/深）、令牌覆盖、字体、网格样式、工具栏位置与显隐、面板折叠 → `settings.json`（全局 + 工程级覆盖）。
  - 布局：面板左右停靠/折叠、子图槽位拖拽互换（改 `subplot` 索引，写回 spec）、布局方案保存/恢复 → `.layout.json`（"4 联对比"、"单图细看"…）。
  - **不引 docking 框架**（golden-layout 之流会拖进 jQuery 与浮窗语义）；CSS Grid + pointer 事件足够。
- **主题单一来源**：RhineLabUI token 导出为 `theme.json`，netlab 与 PlotKit 共读一份，避免色值漂移。图表外壳（header/工具栏/空态/错误态/右键菜单）复用现有组件 class。

---

## 10. 传输与接入

```
仿真推进 ──► recorder ──► GET /api/live?cursor=N,binary=1 ──► ArrayBuffer(float32)
                                                              │
                                                     store.push(adapter)
                                                              ▼
                                                       前端 store ──► plotly traces
```

- 序列化：帧头（cursor / t0 / dt / 通道数）+ float32 列式字节；通道名走一次 `GET /api/channels` 缓存。
- 断点续传沿用现有 `cursor/steps` 回退检测（回退 → 清空重来）。
- PlotKit 独立使用（无 netlab）时：`pk.data.add` 直接进 store，`store.push()` 由宿主调用；`fig.show()` 走 D9 三级 sink。

---

## 11. 目录树与票单

```
ProjectPoint/
├─ NetlabHome/                 # 现状，一行不动，直到 P5 才加一个开关
└─ PlotKit/
   ├─ pyproject.toml           # 独立包，pip install -e 可用；extras: [desktop]=PySide6
   ├─ README.md                # 三条硬边界 + 快速开始
   ├─ docs/DESIGN_v0.md        # 本文件
   ├─ src/plotkit/
   │  ├─ __init__.py           # figure / subplots / data / api 顶层出口
   │  ├─ spec/                 # model.py(数据类) validate.py io.py(序列化/版本)
   │  ├─ store/                # registry.py(命名数据集/role/tags) life.py(append/replace) reclaim.py(引用计数+待回收区) disk.py(分块落盘) downsample.py(min-max 包络)
   │  ├─ api/                  # native.py / mpl_proxy.py / plotly_proxy.py
   │  ├─ backends/             # plotly_backend.py(生成 JSON) / mpl_backend.py(savefig) / registry.py(LayerSpec)
   │  ├─ server/               # app.py(FastAPI 子应用) live.py(二进制帧) spec_api.py
   │  └─ runtime/              # sink.py(inline/window/browser) window.py(QtWebEngine 壳)
   ├─ static/                  # vendored plotly partial bundle（零 CDN）
   ├─ tests/                   # spec 往返 / store 生命周期 / 后端 JSON / 抽稀正确性
   └─ examples/                # 最小可跑示例（line / scatter / bar / 子图）
```

| 票 | 目标 | 封口证据 |
|---|---|---|
| **P0 内核** | `spec` 数据类 + 校验 + 序列化 + 版本握手 | 往返相等测试、未知字段保留测试、非法 spec 报错测试 |
| **P1 数据层** | store（命名/role/tags/life）、引用计数与待回收区、`export/history` | 生命周期测试、回收可撤销测试、`replace` 防抖测试 |
| **P2 后端** | plotly 后端出 3 种 kind + mpl 后端 `savefig` | 每个 kind 的 trace JSON 快照、PNG 冒烟 |
| **P3 前端壳** | 页签页面、画布、工具栏、hover/zoom/pan/legend | 浏览器手测清单 + 首帧/缩放计时 |
| **P4 编辑器与布局** | 属性面板、外观自定义、拖拽换槽、layout.json | spec 回写一致测试、布局恢复测试 |
| **P5 接入** | netlab 加 `?chart=plotkit` 开关页签、二进制帧接口、分段计时仪表 | 与老页签并排对拍报告（瀑布表） |
| **P6 收尾** | 等价性测试封口 → 删旧实现（清单见 §12） | grep 零残留引用 + pytest 只增不减 + 对拍数据 |

### 进度台账（2026-10-30 21:08 更新）

| 票 | 状态 | 证据 |
|---|---|---|
| P0 内核 | ✅ | `spec/{model,validate,io}.py`；往返/未知字段/非法 spec 测试全绿 |
| P1 数据层 | ✅ | `store/{registry,reclaim,downsample,disk}.py`；append/replace、回收可撤销、包络保尖峰、分块落盘测试 |
| P2 后端 | ✅ | plotly 三种 kind + mpl `savefig`；trace 快照、降采样、PNG/SVG 测试 |
| P3 前端壳 | ✅（手测通过） | 真实浏览器（QtWebEngine 6.9.2 与 Edge headless）渲染核对；hover/zoom/pan/legend 由 plotly 提供；计时块显示服务端构图 vs 前端合成 |
| P4 编辑器与布局 | 🟡 部分 | 右侧面板已可编译 spec（改图型/颜色/子图槽/X/Y/图例/模式）、拖拽换槽、主题切换、面板折叠已通；**布局方案持久化（`.layout.json`）与面板停靠未做** |
| P4 延迟 | 🔴 未达标 | 8k 点首帧 ≈300 ms（目标 <100 ms）；`/api/series` 二进制通道已就绪但前端仍走 JSON `figure.json` |
| P5 接入 netlab | ⏳ 未开始 | — |
| P6 收尾 | ⏳ 未开始 | 删除清单未执行（旧 canvas 一行未动） |

**渲染期发现并修掉的三个真 bug**（都补了回归测试）：

1. plotly 后端输出了固定像素 `width/height`（1100×600），浏览器里把右侧面板挤出屏幕 → 改为 `autosize=True`，宽度交给容器。
2. trace/annotation 的轴引用写成了 layout 键名 `"xaxis2"`，而 plotly 只认 `"x2"` → 所有子图叠在第一个轴上。
3. layout 里 `anchor` 同样只能写 `"x2"/"y2"`，写成 `"xaxis2"` 会让第二个子图的 y 轴画到最左边、和第一个子图刻度重叠。

另修：`.empty { display:flex }` 盖掉了 `[hidden]` 的 `display:none`，导致空态文案永远显示；柱宽误用线宽（1.6 个坐标单位）把柱子糊满整图；面板图层列表溢出压住计时块（加 `overflow:auto`）。

---

## 12. 删除清单（P6 执行，先列在这里作为"删除许可证"前提）

| # | 位置 | 内容 | 前置条件 |
|---|---|---|---|
| 1 | `NetlabHome/netlab/static/app.js` | `drawChart()` 及时间序列专用分支 | 新页签在 p95 延迟、丢帧、内存三项全绿 |
| 2 | 同上 | `scheduleChartDraw()` 中时间序列分支 | 同上 |
| 3 | 同上 | `state.frames` / `MAX_FRAMES=5000` 环形缓冲（若新通道独立） | 二进制帧接口稳定 1 周 |
| 4 | 同上 | `state.chartSize` 时间序列相关尺寸缓存 | 同上 |
| 5 | 同上 | 页签 DOM/事件绑定（旧"时间序列"页签） | 交互清单 1:1 覆盖（见风险 R3） |
| 6 | `?chart=plotkit` 开关本身 | 并存结束 | 删完后全量回归通过 |

删除证据：`grep -rn "drawChart\|MAX_FRAMES" netlab/static` 零命中 + 测试数不减少 + 打包后体积不增加。

---

## 13. 风险与不做清单

**风险**
- R1 `plotly.js` 体积（4.56 MB 全量 / partial 后 ~1 MB）：用 partial bundle 只打 line/scatter/bar + 子图，离线 vendoring。
- R2 QtWebEngine（Chromium 130）WebGL/ANGLE 在部分显卡上失败：默认 canvas 渲染，WebGL 只在 3D 与 >25k 点时开，且自动降级。
- R3 "语法兼容"退化成假兼容：以"支持列表 + 明确忽略列表 + warning"三条钉住，不承诺 mpl 全部参数。
- R4 spec 字段漂移：版本号 + 未知字段透传 + P0 的往返测试。
- R5 双语法代理与原生 API 三入口产生不同 spec：三者共用同一 `spec` 构造器，测试断言"同一调用 → 字节相同 spec"。

**不做（v0 明确不做）**
Rust 重写、3D 图层（第一版）、clabel/quiver/streamplot 的 JS 自研实现、WebSocket/SSE、第三方 docking 框架、PyPI 公开发布（先 `pip install -e`）、反向 spec→Python 解析。

---

## 14. 待你确认的最后两件事

1. 名字：`PlotKit` / `plotkit` 可用？要改就现在改（目录名 + `pyproject.toml` 的 `name` 两处）。
2. 开工顺序：按 P0→P6 串行，还是 P0/P1 与 P3 前端壳并行（前端先用假数据把画布与交互做出来，不等后端）？

### v0.2 追加（2026-10-30 21:08）：论文级出图能力

用户给的 panel b 参考图拆成 10 个要素，按 D17（浏览器交互预览 + matplotlib 正式图）落地，
两个后端消费**同一份 spec**：

| 要素 | spec 字段 | mpl | 浏览器 |
|---|---|---|---|
| 双对数 + 次刻度 | `view.xscale/yscale` + `view.ticks.minor` | `set_xscale` + `minorticks_on` | `type:"log"` + `minor` |
| 对数轴朴素标签 | `view.loglabels` = `sci/plain/plain-x/plain-y` | `LogLocator(subs=(2,4,6,8))` + `FuncFormatter` | `exponentformat:"power"` + `dtick:1` |
| 方向误差棒 | `data.error_x/error_y(_minus)` → 数据集名 | `ax.errorbar(fmt="none")` | `error_x/error_y` |
| 内侧 + 镜像刻度 | `view.ticks.inside/mirror` | `tick_params(direction="in", top/right=True)` | `ticks:"inside"`, `mirror:"all"` |
| 内嵌子图 | `figure.insets[{subplot,parent,rect,fonts}]` | `parent.inset_axes([rx,ry,rw,rh])` | 父轴 domain × rect 映射 |
| 拖拽调位置/大小 | 前端改 `rect` 后 PUT 全量 spec | 只读 | pointer 事件 + 覆盖层 |
| 逐级字号 | `figure.fonts` + inset 级覆盖 | `fontsize=` | `tickfont` / `title.font` |
| 数学排版 | `$R_G$` / `$\Delta	heta^2$` | 原生 mathtext | `math_text()` → `<sub>/<sup>` |
| 斜率三角 / 箭头 | `figure.shapes[kind=triangle/arrow]` | `plot` + `annotate` | `layout.shapes` + `annotations` |
| 图例过滤 | `layer.legend=false` | handles 过滤 | `showlegend` |

**渲染期又抓到 6 个真 bug**（除第 5 条外都有回归测试）：

1. plotly 对数轴 `range` 是**指数**不是数据值 —— 传 `[1.3, 11]` 会让轴塌成 1.05~1.35；现在 log 时取 `math.log10(lo/hi)`，非正数抛 `ValueError`。
2. inset 槽位的 `xaxis.anchor` 漏设 —— 内嵌图 y 轴落到画布最左边、和主轴刻度叠在一起。
3. `axis_titles` 合并用 `if v not in (None, "", False)`，把 `grid=False` 当假值丢掉。
4. `math_text` 的 `re.sub(..., r"<sub></sub>")` 里 `` 被写成控制字符 ``，浏览器标题变成 `R<sub></sub>`；改用 `\g<1>`。
5. 前端静态资源被浏览器缓存 —— 改完 JS 刷新还是旧页面；`create_app` 现在对 `/` 与 `/static` 回 `Cache-Control: no-store`。
6. `kind` 校验只认注册名不认别名（`scatter` → `marker`），前端 PUT 直接 400；现在 `registry.known_kind_names()` 同时接受两者。

测试：**105 passed**（新增 `tests/test_pub.py` 17 项：误差棒、对数轴 range 语义、刻度/字号、
装饰、inset domain 与 anchor、`math_text`、双后端一致性）。


## v0.2 追加（2026-10-30 21:55）：交互层与性能实测

- **D18 布局与 spec 分家**：面板宽度、折叠状态、展开图层、图层分组写 `layout.json`（`GET/PUT /api/layout`），spec 只管图本身。三者原子写、上限 64 KB、非法输入 400/413。
- **D19 撤销 = 快照栈**：前端存最近 50 份"已提交"的 spec 字符串，撤销/重做整份 PUT，不改协议。
- **D20 菜单与快捷键**：菜单栏 + 图层右键 + `Ctrl+Z/Y/D/S/E`、`Delete`、`Esc`，结构向 netlab 靠（紧凑、无边框、hover 高亮）。
- **D21 首帧门槛修正**：实测冷启动 862 ms（其中 `Plotly.react` 首次 ~180 ms、服务端 65 ms），「<100 ms 首帧」不可达；改为「热重绘 <50 ms、冷启动 <1 s、交互不丢帧」。
- **D22 传输优化**：`GZipMiddleware(minimum_size=1024)` + `figure.json` 按 `(revision, pixels, per_pixel)` 缓存，响应头 `X-PlotKit-Cache`。

| 实测项 | 数值 |
|---|---|
| 首帧（含引擎解析） | 862 ms |
| 首次绘制（服务端构图 / 前端合成） | 64.7 ms / 179.5 ms |
| 热重绘 ×3 | 83 / 23 / 21 ms（第 4 次 13.7 ms） |
| `/api/figure.json` | miss 6.8 ms → hit 4.8 ms |
| 测试 | 115 passed |

## v0.3 追加（2026-10-30 22:30）：补齐老画布能力

对齐 `netlab` 时间序列画布的工具栏，目标是删掉老 canvas 之前先不丢功能：

| 老画布能力 | PlotKit 落法 | 备注 |
|---|---|---|
| 时间窗 5 s | `figure.window`（spec 字段）+ 后端切片 + 强制 xlim | 数据不进构图就不画，比"放大后裁剪"省 |
| 回放滑杆 | `GET /api/figure.json?t=`，后端 `to_figure(t_end=...)` | 游标属 L3，不回写 spec |
| 播放 / 速度 / 循环 | `tickPlay()` 按真实时间前进（帧/秒 × dt） | 重绘被降频时回放速度仍正确 |
| 回到实时 | 游标置空 | |
| 清空轨迹 | `POST /api/clear`（图层清空 + 数据集归零） | 宿主继续推 → 通道自动重建 |
| 信号筛选 + 勾选 | 数据集面板加搜索框 + 「全部加图层」 | 批量建折线，跳过已存在的 x/y 组合 |
| 图例 | 已有（`layer.legend`） | 老画布的图例点击切换未做，留给 P6 |

**新增决策 D23**：时间窗属于 spec（`figure.window`），回放游标属于 L3 前端状态、永不回写——同一份 spec 既能出静态图（全量）又能做交互回放。

**坑**：`playhead` 的 `input` 事件里若先 `stopPlaying()` 再读 `event.target.value`，会因为 `syncPlayheadUI()` 把滑杆值写回旧游标而读错；必须**先读值再停播**。
