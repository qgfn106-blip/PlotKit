# PlotKit 需求 · 决策 · 进度 · 经验（单一入口）

> 最后修改：2026-10-31 00:20
> 用途：新会话先读这一份，再动手。设计细节看 [DESIGN_v0.md](DESIGN_v0.md)，用法看 [../README.md](../README.md)，
> 与 netlab 的接口口径看 `NetlabHome/netlab/docs/REQUIREMENTS_AND_RULES.md` 的 **R32 / D66 / D67 / P12**；
> **PlotKit 自己的需求、决策、计划、进度与经验全部在本文件**（§1 需求 / §2 决策 / §3 计划 / §4 进度 / §5 经验），不写进 netlab 的文档。

---

## 1. 需求（用户原话 + 解读 + 现状）

编号 `PK-R*`，与 netlab 的需求号分开记，避免两套编号互串。

| 编号 | 用户要什么（原话/要点） | 解读 | 现状 |
| --- | --- | --- | --- |
| **PK-R01** | 「将这套绘图直接用 Bokeh 库替代……能否提高效率，与运行速度，并且提高交互性能」 | 目标不是"换个库"，是交互 + 性能 + 可维护三件事；Bokeh 无 3D 且 CDS 全量重绘，出局 | 以"一套 spec + 双后端"落地 |
| **PK-R02** | 「编程过程中依然能使用该库，并且做到语法兼容，依然操作者能自行按照原来 matplotlib 语法或者 plotly 语法进行习惯性操作」 | 三种写法产出同一份 spec：`fig.add_plot()` / `ax.plot()` 代理 / `add_trace()` | 完成（`api/native.py`、`api/mpl_proxy.py`） |
| **PK-R03** | 「一套新的语法只传入数据，并且数据特殊命名，打上标签，然后在前端选择如何使用数据」 | 命名数据集注册表 + 延迟绑定：`add_data(name, arr, tags, unit, role, life)`，spec 只存引用 | 完成 |
| **PK-R04** | 「子图可以在一个子图内部的一小处，可以靠拖拽控制，并且各图参数都能方便调节」 | inset 是 spec 概念（父轴比例 rect），浏览器里可拖可缩，matplotlib 侧用 `inset_axes` | 完成 |
| **PK-R05** | 「最后要能方便实现绘制这种图片」（论文 panel b：双对数、四色方向误差棒、虚线拟合、内嵌子图、ρ_B 箭头、−3 三角、LaTeX 标题） | 论文级能力：误差棒、内侧/镜像刻度、逐级字号、mathtext、装饰图元、`plain-x` 对数刻度 | 完成（`examples/paper_panel_b.py`） |
| **PK-R06** | 「可以参考 https://github.com/KDE/labplot 的架构」「图层展示区域太小」「UI 交互、菜单栏参考 netlab 的理念」 | 结构上借鉴 LayerSpec 注册表 / 视图语义 / preset 合并；界面走"信息密度 + 挂耳 + 可折叠分组 + 菜单栏" | 完成 |
| **PK-R07** | 「做这个组件请独立在一个新文件夹，不要与现有工程的文件混在一起」 | 独立包 `ProjectPoint/PlotKit`，单向依赖，可 `pip install -e` | 完成 |
| **PK-R08** | 「新功能完全实现，就要能准确将原方法删去」「UI 与软件 UI 相兼容，并且可自定义 UI」 | 完成即删旧的等价迁移；外观级 + 布局级可自定义（`theme` + `layout.json`） | 部分：能力已对齐中；**旧 canvas 与分析面板不删**（2026-10-31 用户决定，D37） |
| **PK-R09** | 「我在 vs code 运行程序时，能弹出窗口，而不是直接跳到浏览器去」 | `show()` 三级 sink：inline → window（PySide6 + QtWebEngine）→ browser | 完成（`runtime/sink.py`、`runtime/window.py`） |
| **PK-R10** | 「netlab 内部做可分离的内嵌窗口」「补齐老画布能力」 | 停靠 ⇄ 浮出两种形态；时间窗/回放/播放/清空/信号筛选对齐老 canvas | 完成（P12-05、P12-06） |
| **PK-R11** | 「在 plotkit 中实现 multiplotter 的所有绘图功能」 | 18 种 kind（11×2D + 7×3D）+ `correlation` 聚合全部可用，同一份 spec 出图 | **进行中**：`registry.kinds()` **18 种全部完成**（11×2D + 7×3D，见 §3.3），另有 3 种附加 kind（`contourf` / `correlation` / `barbs`），registry 共 21 种 |
| **PK-R12** | 「以及 matplotlib API 中所有的绘图功能」 | 以 `Axes` 绘图方法为全集（约 55 个），逐个给出归属：双后端 / mpl 兜底 / 不做 | **未盘点**：归属表见 §3.4 |
| **PK-R13** | 「按照 multiplotter 中的逻辑进行预设计与编写程序」 | 预设表、分发别名、透传白名单、严格模式、`init()` 全局样式、`style_scope`、`register_layer` 契约 | 仅 `reg.register` 有雏形（无 presets/passthrough/strict） |
| **PK-R14** | 「并且可自己优化」 | 允许偏离原实现：服务端分箱/相关矩阵、重绘缓存与 ETag、按像素宽度抽稀、节流刷新 | 部分已有（D22 缓存、min-max 抽稀） |
| **PK-R15** | 「开始前做好项目规划，确定需求，以及项目推进流程，验收标准」 | 需求 + 分期 + 四件套验收见 §3.5/§3.6 | 完成（2026-10-30） |
| **PK-R16** | 「以及持续更新文档」 | 每票收尾四处同步，不允许只改代码 | 执行中（§3.8 口径） |

## 2. 决策台账（D1–D36，摘录结论）

| 号 | 决策 | 一句话理由 |
| --- | --- | --- |
| D1 | 一套 spec + 双后端（plotly / matplotlib）（**2026-10-31 由 D33 修订为 mpl 单后端**） | Bokeh 无 3D 全量重绘；matplotlib 有 clabel/quiver/streamplot 等不可替代件 |
| D2 | 三层分离：L1 数据 / L2 spec / L3 视窗；L2 权威在 Python | 缩放平移永不回后端；语义改动回后端，本地回环 2–5 ms 可忽略 |
| D3 | 命名数据 + 延迟绑定 | 程序只管数据，前端只选用法 |
| D4 | `spec.json` 唯一真相，单向 codegen | 不做反向解析，避免双权威 |
| D5 | `life="append"` 默认 / `"replace"` | 一个能回看历史，一个只保最新 |
| D6 | 程序自存业务数据，库只管可视化临时数据 + 待回收区 | 关窗不等于删数据 |
| D7 | 先不加 Rust | 瓶颈在 IO 不在 CPU；接口先钉死 |
| D8 | 第一版 `line/scatter/bar` + 2D 子图 | 垂直切片先跑通 |
| D9 | sink 三级探测 | 笔记本 / 桌面 / 浏览器自动选 |
| D10 | 全量 spec 回传 + 派生 op | 前端不重算分箱/相关系数 |
| D11 | 独立目录 `ProjectPoint/PlotKit` | 不与 netlab 混 |
| D12 | 借鉴 MultiPlotter 结构但不 import | 它的注册表模块一 import 就拖进 matplotlib |
| D13 | 与 netlab 新页签并存（~~完成即删旧~~ → **2026-10-31 由 D37 修订：不删旧**） | 可对拍、可退回、零回归 |
| D14 | UI 自定义 = 外观级 + 布局级 | 只做这两层，不引 docking 框架 |
| D15 | 验收用分段计时瀑布 | 定位到段，不争"快不快" |
| D16 | HTTP cursor + ArrayBuffer float32 | 不上 WebSocket/SSE，复杂度不值得 |
| D17 | 浏览器做交互预览、matplotlib 出正式图（**2026-10-31 由 D33 修订：统一 mpl 渲染**） | 浏览器无法做 LaTeX 级排版与 clabel |
| D18 | "软件怎么摆"进 `layout.json`，不进 spec | 分组/停靠不是图的一部分 |
| D19 | 撤销 = 前端 spec 快照栈 | 50 步足够，不引命令模式 |
| D20 | 菜单栏 + 快捷键 + 右键 | 对齐 netlab 的操作习惯 |
| D21 | 门槛修正：热重绘 <50 ms、冷启动 <1 s（**2026-10-31 起 mpl 重绘门槛改为 <120 ms，见 §3.6**） | `Plotly.react` 冷启动 ~180 ms，"首帧 <100 ms" 不可达 |
| D22 | GZip + 服务端构图缓存（`X-PlotKit-Cache`） | 同一 spec 反复取图不该重算 |
| D23 | 时间窗进 spec（`figure.window`），回放游标属 L3 不回写 | 静态导出与交互共用同一份数据口径 |
| D24 | `kind` 唯一图层类型；`layer.data` 按 kind 声明多键（`z/u/v/labels/values/image/cells`），`REQUIRED_DATA` 表驱动校验 | 不为每种图造新字段 |
| D25 | `LayerSpec` 增 `browser_native` / `fallback`；无浏览器等价的图**整图**走 mpl 出 PNG，不缝合 | 兜底策略变成字段与测试 |
| D26 | ~~前端按 `figure.caps` 懒加载 plotly 分部包~~ **作废（2026-10-31，D33 后不再有 plotly bundle）** | 历史记录：basic 1,102,006 B / cartesian 1,405,670 B / gl3d 1,678,645 B |
| D27 | 每 kind 一份 presets（默认 + 命名预设）；合并优先级 `KIND_DEFAULTS < init 全局 < add 参数 < **kwargs` | 对齐 MultiPlotter 的 KIND_DEFAULTS |
| D28 | 浏览器专属键走 passthrough 白名单，未列出记 warning；`strict=True` 抛错 | 防假兼容与静默丢参 |
| D29 | 动画 = spec 的 `figure.frames`（每帧只存 patch）；plotly 用 `Plotly.animate`，mpl 用 `FuncAnimation` 导 GIF/MP4 | 一套 spec 两种出口 |
| D30 | ~~统计/信号类先只做 mpl 兜底~~ **作废（2026-10-31，D33 后全部走 mpl）** | 历史记录 |
| D31 | 一切"要算的"在服务端（hist 分箱、correlation 矩阵、hexbin 计数、抽稀），前端只画 | 沿用 D10，避免两套数值 |
| D32 | 新增 kind 封口固定四件套（spec 往返 / plotly 快照 / mpl PNG / CDP 截图），并加"两后端都能出图"参数化用例 | 88 项全绿但渲染炸过 4 次 |
| D33 | **渲染统一 matplotlib（2026-10-31，用户定，修订 D1/D17）**：plotly 退役，浏览器只做呈现与编辑 | 用户原话「只能用 matplotlib 的绘图，用网页前端集中呈现，matplotlib 作为后端」。单一渲染路径 ⇒ 交互图与论文图同一套语义，不再维护两份 builder，也不会出现"浏览器画对了 mpl 画错"的漂移 |
| D34 | 交互 = **即时变换 + 提交重绘**：拖动/滚轮期间前端对高 DPI PNG 做 transform（0 延迟），停手 120 ms 才按新 xlim/ylim 回后端重绘；hover 读数由前端算，不触发重绘 | 保持"手感即时"，又不让每帧都走服务端 |
| D35 | 实时流 = 服务端**节流重绘**（默认 8 fps，可调 2–20）+ `ETag`/spec revision 缓存；数据按像素宽度抽稀（≤2 点/列） | PNG 重绘 ~60–100 ms/帧，60 fps 不可能；先保正确与可读 |
| D36 | inset 拖拽 = 前端覆盖层画框，松手 PUT spec 再重绘；`LayerSpec` 用 `interactive: bool` 取代 `browser_native` | 拖拽中不回后端，避免抖动 |
| D37 | **不删旧 canvas**：netlab 原生时间序列/示波器/李萨如/相图与分析面板长期保留，PlotKit 作为**并行**能力（2026-10-31 用户决定） | 用户明确要求「先不要将原生绘图分析删掉」；两条路径并存，谁都不阻塞谁 |

## 3. 图表能力扩展计划（P13 / D24–D36，2026-10-30 立项，2026-10-31 架构修订）

> 目标：从 3 种图层补齐到 MultiPlotter 的 18 种，并覆盖 matplotlib `Axes` 的约 55 个绘图方法。
> **架构（2026-10-31 用户定，D33）**：**渲染只用 matplotlib，网页前端只做集中呈现与编辑**；plotly 退役（新功能一律走 mpl）；netlab 的旧 canvas 与分析面板**不删**（D37）。
> 状态：规划完成，代码零改动；待确认实时刷新档位后从 P13-00 开工。

### 3.1 现状（实测，非转述）

- `registry.kinds()` = `('bar','line','marker')` → **3/18**；`spec/validate.py` 的 `REQUIRED_DATA` 也只有这三个 kind。
- 前端当前走 plotly：`app.js:377` 用 `Plotly.react()`，数据取 `/api/figure.json`；vendored `plotly-basic.min.js` 1,102,006 B（分部包 cartesian 1,405,670 B / gl3d 1,678,645 B 原计划按 caps 懒加载）。
- `/api/png` 已存在但只接受 `dpi`，**没有视窗参数**（xlim/ylim/宽高），也还没有重绘缓存。

### 3.2 渲染与交互模型（D33–D36）

| 职责 | 归属 | 说明 |
| --- | --- | --- |
| 图形语义（spec） | Python | 不变，L2 权威 |
| **渲染** | **matplotlib（Agg）** | 唯一渲染路径；交互图与论文图同一份代码、同一套语义 |
| 视窗缩放/平移 | 前端即时变换 + 后端重绘 | 拖动期间对高 DPI PNG 做 CSS transform（0 延迟）；停手 120 ms 后按新 `xlim/ylim` 请求重绘 |
| hover 读数 | 前端 | 用像素→数据坐标换算，读 `/api/series`，**不触发重绘** |
| inset 拖拽 | 前端覆盖层 + 提交 | 拖拽中画框，松手 PUT spec 再重绘 |
| 实时流（netlab 5 s 窗口） | 后端节流重绘 | 默认 8 fps（可调 2–20），`ETag` + spec revision 缓存 |

**三段式交互**：① 拖拽/滚轮 → 前端变换（即时）；② 停手 120 ms → `/api/render?w=&h=&xlim=&ylim=` 换图；③ hover → 前端算读数，不发请求。

### 3.3 18 种矩阵（全部 matplotlib 渲染）

数据键按 D24 由 `REQUIRED_DATA` 表驱动；"mpl 调用"列出主要 API，便于估工。

| kind | 维 | 数据键 | mpl 调用 | 票 |
| --- | --- | --- | --- | --- |
| line / scatter(marker) / bar | 2D | x,y(,error_x/y) | plot / scatter / bar | — |
| hist | 2D | x（服务端分箱） | hist 或 bar | ✅ P13-01 |
| pie | 2D | labels,values | pie | ✅ P13-01 |
| image | 2D | image,zmin/zmax | imshow | ✅ P13-01 |
| table | 2D | cells,header | table | ✅ P13-01 |
| heatmap | 2D | z,x,y | pcolormesh / imshow + colorbar | ✅ P13-02 |
| contour / contourf | 2D | z,x,y,levels | contour / contourf + clabel | ✅ P13-02 |
| correlation（别名 corr / correlation_matrix） | 2D | 多序列 → 矩阵 | imshow + colorbar + 列名刻度 | ✅ P13-02 |
| quiver（`key=True` 出 quiverkey）/ streamplot / barbs | 2D | x,y,u,v | quiver / streamplot / barbs | ✅ P13-03 |
| surface / line3d / scatter3d / bar3d / hist3d / quiver3d | 3D | x,y,z(,u,v,w) | plot_surface / plot / scatter / bar3d / hist3d / quiver | ✅ P13-04 |
| stream3d | 3D | x,y,z,u,v,w | RK2 积分后 plot3D（mpl 无原生 stream3d） | ✅ P13-04 |

### 3.4 matplotlib 方法归属（约 55 个）

渲染全部走 mpl，分类依据变成「要不要 figure 级字段」而不是「浏览器有没有」：

| 组 | 方法 | 形态 |
| --- | --- | --- |
| 线/点/柱/面积 | plot, scatter, bar, barh, errorbar, fill_between, stackplot, stem, step, stairs, broken_barh, eventplot, vlines, hlines, axline | 独立 kind 或 `figure.shapes` |
| 统计 | hist, hist2d, boxplot, violinplot, bxp, pie, ecdf, hexbin | 独立 kind |
| 图像/场 | imshow, matshow, pcolor, pcolormesh, contour, contourf, clabel, spy, figimage | 独立 kind（clabel 作为 contour 的 `labels=True`） |
| 矢量 | quiver, quiverkey, streamplot, barbs | 独立 kind（quiverkey 作为 quiver 的 `key=True`） |
| 三角/非结构 | triplot, tricontour, tricontourf, tripcolor | 独立 kind |
| 信号 | psd, csd, specgram, cohere, acorr, xcorr, angle/magnitude/phase_spectrum | P13-05 评估：直接用 mpl 或改走 `line` |
| 3D | plot, scatter, bar3d, hist3d, plot_surface, plot_wireframe, contour3D, contourf3D, quiver3D, voxels, trisurf, stem3D, text3D | 独立 kind 或 kind 参数 |
| 轴级 | twinx/twiny, secondary axis, broken axes, colorbar, legend, grid, spines | `figure.axes[]` 字段，不建 kind |

### 3.5 票单（P13-00…08）

| 票 | 内容 | 封口证据 |
| --- | --- | --- |
| **P13-00** 基建 | ① 渲染管线：`/api/render?w&h&xlim&ylim&dpi&fmt`（Agg + figure 复用 + 线程锁）；② 缓存：spec revision + 视窗 + 尺寸 → ETag/`If-None-Match`；③ 前端图像层：`<img>` + 拖拽/滚轮变换 + 停手重绘；④ hover 读数（像素→数据）；⑤ presets / `fig.add(kind,cfg)` / passthrough+strict / `pk.init()` / `style_scope`；⑥ `LayerSpec` 去掉 `browser_native`，加 `interactive: bool` | 不新增 kind；测试 ≥ +12；line 图在 1200×700、6×20k 点下重绘 < 120 ms；拖动期间无请求 |
| **P13-01** 低档四 kind | hist（服务端分箱）、pie、image、table | 4×四件套；hist 与 `np.histogram` 逐箱相等 |
| **P13-02** 场类 | heatmap、contour/contourf（含 clabel）、correlation | 3×四件套；correlation 与 `np.corrcoef` 差 < 1e-12 |
| **P13-03** 矢量场 | quiver（含 quiverkey）、streamplot（+barbs） | 4×四件套；缺 u/v 被校验拒绝 |
| **P13-04** 3D 七种 | surface/line3d/scatter3d/bar3d/hist3d/quiver3d/stream3d | 7×四件套；`elev/azim` 写入 spec 可复现 |
| **P13-05** 统计/信号族 | boxplot、violinplot、ecdf、hexbin、barh、stackplot、stem、step、stairs、broken_barh、eventplot、psd/specgram 等 | 每方法一条 PNG 冒烟 |
| **P13-06** 动画 | `figure.frames` + `FuncAnimation` 导 GIF/MP4；前端按帧序列播放（PNG 序列或预生成 GIF） | 60 帧正弦动画；GIF 可打开；播放 ≥ 24 fps |
| **P13-07** 附属能力 | colorbar 细化、表格单元格高亮、`ScienceResult`/`SciencePlotter`、`shrink_field`、字体链（中文优先） | 对流传热算例可跑；Nu 与 de Vahl Davis 差 1–2%；中文不出方框 |
| **P13-08** 收尾 | 覆盖率表（18/18 + 55/55）、性能回归、plotly 退役清单（不含删旧 canvas，见 D37） | 覆盖率 100%；netlab 347 仍绿；冷启动 < 1 s |

### 3.6 验收标准

**每个 kind 四件套（D32，按 mpl 单后端修订）**：① spec 往返字节相等、未知字段保留；② PNG 像素快照（固定 `metadata`，逐像素比对或 SSIM > 0.995）；③ 视窗重绘一致性（改 xlim/ylim 后轴刻度与数据位置符合预期）；④ CDP 截图 + 轴/图例/色条存在性断言。

**通用门槛**：PlotKit 测试只增不减（124 起）；`node --check static/app.js`；改前端 bump `index.html` 两处 `?v=`；**重绘 < 120 ms（1200×700，6 通道 × 20k 点）**；实时刷新默认 8 fps 且可调；netlab 347 不回归。

**量化**：hist 与 `np.histogram` 逐箱相等；correlation 与 `np.corrcoef` 差 < 1e-12；contour levels 与 mpl 默认一致；3D 的 `elev/azim` 写入 spec 后可复现；动画 60 帧；对流传热 Nu 与 de Vahl Davis 差 1–2%。

### 3.7 风险与不做

| # | 风险 | 对策 |
| --- | --- | --- |
| R1 | **实时刷新上限**：PNG 重绘 ~60–100 ms/帧，做不到 60 fps | 节流 8 fps（可调 2–20）；拖动期间前端变换不请求；必要时降采样到像素宽度 |
| R2 | 交互从"原生"退化为"变换 + 重绘" | 停手 120 ms 才重绘；高 DPI 预渲染 2× 供放大；hover 不发请求 |
| R3 | 服务端 CPU 被渲染占满 | figure 复用（不重建）、LRU + ETag、同 spec 同视窗直接命中缓存 |
| R4 | 字体/DPI 跨机器不一致 | 字体链固定（中文优先）+ `savefig` 固定 dpi 与 `metadata`；像素比对只在同机跑 |
| R5 | 18 种 kind 让校验表膨胀 | `REQUIRED_DATA`/`KNOWN_STYLE_KEYS` 由注册表生成 |

**不做**：plotly 渲染（已退役）；自研 JS 图形渲染器；mapbox/geo；第三方 docking 与 `brokenaxes`；反向 spec→Python codegen（D4）。

### 3.8 文档同步（每票收尾）

本文（PK-R 现状 / D 台账 / 进度表 / 经验）→ `../README.md` 的「当前状态」→ netlab 侧**只在 R32 留一行指针**，不复制结论。


## 4. 当前进度

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| P12-01 | spec + DataStore + 分块落盘 + 抽稀 | 完成 |
| P12-02 | plotly + matplotlib 双后端 | 完成 |
| P12-03 | 浏览器交互（面板/inset 拖拽/撤销/菜单/快捷键/layout.json） | 完成 |
| P12-04 | 论文级出图（误差棒/刻度/字号/mathtext/装饰/对数） | 完成 |
| P12-05 | netlab 接入（`/plotkit` 子应用 + 子页签 + 可停靠浮窗 + `?embed=1`） | 完成 |
| P12-06 | 老画布能力对齐（时间窗/回放/播放/清空/信号筛选） | 完成 |
| P12-07 | ~~删旧 canvas~~ | **已取消**（2026-10-31 用户决定保留原生绘图与分析，见 D37） |
| P13-00 | 基建：mpl 渲染管线（`/api/render`）/ ETag 缓存 / 前端图像层（变换+停手重绘）/ hover 读数 / presets / `fig.add()` / passthrough+strict / `init()` | **功能完成，性能未达标**：13 项新测试（`tests/test_render.py`）；1200×700 × 6 通道 × 20k 点实测 **~310 ms**（目标 <120 ms）；**浏览器已实测**（见 §6）：滚轮缩放 → `state.view` 更新 → 120 ms 后服务端按新 xlim 重绘并换图，`transform` 复位 |
| P13-01 | hist / pie / image / table（服务端分箱、矩阵/表格数据键） | ✅ 完成：`tests/test_kinds_basic.py` 14 项，全库 **165 passed**；四种都出非空白 PNG；hist 与 `np.histogram` 逐箱相等；浏览器截图见 §6 |
| P13-02 | heatmap / contour / contourf / correlation | ✅ 完成：`tests/test_kinds_field.py` 14 项，全库 **165 passed**；相关矩阵与 `np.corrcoef` 差 <1e-12；浏览器截图见 §6 |
| P13-03 | quiver（含 quiverkey）/ streamplot / barbs | ✅ 完成：`tests/test_kinds_vector.py` 15 项，全库 **180 passed**；vmin/vmax、纯色流线、color_by 白名单均已封口；浏览器截图见 §6 |
| P13-04 | surface / line3d / scatter3d / bar3d / hist3d / quiver3d / stream3d | ✅ 完成：`tests/test_kinds_3d.py` 14 项，全库 **194 passed**；**18/18 覆盖**；浏览器四联截图见 §6 |
| P13-05…07 | 统计/信号族（mpl 兜底）、动画、附属能力（colorbar/表格/Science/字体） | 未开工 |
| P13-08 | 收尾：覆盖率表 100% 有归属、性能回归、删旧评估 | 未开工 |

> 图表扩展的需求、矩阵、票单、验收与经验**全部在本文件**（§1 PK-R11–R16 / §2 D24–D32 / §3 计划 / §4 进度 / §5 经验）；netlab 侧只在 R32 留一行指针，不复制结论。

**测试基线**：PlotKit `PYTHONPATH=src python -m pytest` → **124 passed**；netlab `python -m pytest netlab/tests -q` → **347 passed**。

**性能实测（28 数据集 / 11 图层 / ~1.4k 点）**：冷启动首帧 862 ms、热重绘 13.7–83 ms、`figure.json` miss 6.8 ms / hit 4.8 ms。

**原删旧前置（P12-07，已取消）**：① 图例点击切换显隐；② 示波器 / 李萨如 / 相图三块画布；③ 「预计算 0→T」；④ 探针勾选树。

> 2026-10-31 用户决定**不删旧 canvas**（D37）：这四项降级为「可选增强」，不再阻塞任何票，也不再计入验收。

## 5. 经验（这份代码最容易踩的）

1. **plotly 的三处"静默忽略"**：子图轴引用必须是 `x2`/`y2`（写 `xaxis2` 会被忽略并回落到第一个轴）；对数轴 `range` 是**指数**不是数据值；`layout.annotations` 里混进一个非法条目会让**整组文字都不渲染**（文字走 `mode:"text"` trace，线/带走 shapes，箭头走"线 shape + 三角 marker trace"）。
2. **子应用挂载会打破两个前缀假设**：前端绝对路径 `/api/...` 失效（改相对路径 + `<base href="./">`）；`no-store` 中间件判 `startswith("/static")` 失效（改 `"/static/" in path`）。
3. **`[hidden]` 会被 `display: flex` 盖掉**：凡写过 `display` 的元素都要补 `.x[hidden] { display: none }`。
4. **先读输入再停播**：事件回调里 `stopPlaying()` 会把滑杆值写回旧游标，之后再读 `event.target.value` 拿到的就是旧值。
5. **`requestAnimationFrame` 在无头/后台页会被暂停**：回放用 `setTimeout` + 「真实经过时间 × 速度」。
6. **`mpl` 的 `inset_axes` 是子轴**：`len(fig.axes)` 仍是 1，判断要看 `parent.child_axes`。
7. **验证网页渲染不能用 QtWebEngine offscreen**（只得到灰图）；用 `msedge --headless=new --remote-debugging-port=…` + `tools/cdp_flow.mjs`（**一条 CDP 连接跑完整串动作**，反复建 WS 会把页面拖死）。2026-10-31 补：本机直接用这条命令**不行**，见第 13 条。
8. **plotly 分部包的能力边界不能靠 grep 字符串判断**：在 `plotly-basic.min.js` 里 `grep heatmap/contour/surface` 都能命中（错误提示与 schema 里带这些词），据此会误判成"只差 builder"。真实判据是文件末尾 `Plotly.register([...])` 的模块列表——basic 只注册 scatter/bar/pie 三个；或直接在页面里用最小 trace 试 `Plotly.newPlot` 看是否报 "not registered"。
9. **mpl 渲染的耗时结构**（2026-10-31 实测，1200×700 / 6 通道 / 20k 点）：`to_figure` ≈ 118 ms、`savefig` ≈ 190 ms，合计 ~310 ms。**按像素抽稀只压数据量，压不动 savefig 这个常数**——要冲 <120 ms 得动 `constrained_layout`、`canvas.print_png` 与字体预热（P13-08）。
10. **去掉 plotly 后 `#plot._fullLayout` 不存在**：inset 覆盖层原来靠它换算像素，会静默失效（覆盖层永远 hidden）。改用服务端返回的 `X-PlotKit-Axes`（各槽位包围盒）后恢复。
11. **`KIND_ALIASES` 里把 `hist` 映射成 `None` 会挡住新图层**：那是早期"明确不支持"的写法，P13-01 加了 hist 之后 `fig.add("hist", …)` 仍报「不支持的图层类型」。新增 kind 时先 grep 别名表，别只改注册表。
12. **非别名的样式键要走 `KNOWN_STYLE_KEYS` 分支**：`bins`/`cmap`/`colorbar` 不在 `STYLE_ALIASES` 里，原来会被当成"不认识的参数"记 warning 并丢掉，柱子永远是默认 30 箱。修法：`_style_from_kwargs` 先查别名，再查 `KNOWN_STYLE_KEYS`，最后才算忽略。
13. **本机无头 Edge 截图的三个坑**（2026-10-31 实测，Edge 156）：① 用户已经开着 Edge 时，直接调 `msedge.exe` 会把命令行**转交给已有实例并立刻退出**——exit 0、无 stdout、无文件、无调试端口，看起来像"浏览器坏了"；必须用独立进程启动 + 独立 `--user-data-dir` + `--no-sandbox`。② `--headless=old` 已移除，`--dump-dom` / `--screenshot` 要配 `--headless=new`。③ 本机环境同时有 `HTTPS_PROXY` 与 `https_proxy`，带重定向启动会报「已添加项。字典中的关键字:HTTPS_PROXY」，先删掉小写那个。工具：`tools/shot.ps1`（一次调用内完成截图/DOM，跑完自动清 profile）。
14. **工具调用结束会连带杀掉子进程**：浏览器 + CDP 探测必须写在**同一次调用**里（启动 → 等待 → node 探测 → 结束进程）；分两次调用会看到 `ECONNREFUSED 127.0.0.1:9420`。
15. **`contour(levels=N)` 的 N 只是"建议值"**：mpl 用 MaxNLocator 取整，传 7 可能得到 9 条线。要精确控制就传**显式列表** `levels=[-1,-0.5,0,0.5,1]`；测试也应断言列表相等，而不是数个数。
16. **同一个键在不同 kind 里可能既是数据又是样式**：`labels` 在 pie 里是数据集名、在 contour 里是布尔 `labels=True`。`fig.add()` 现在按 `REQUIRED_DATA` 判定：该 kind 必需的键才是数据，其余交给样式白名单，否则 `labels=True` 会被当数组注册并抛 `TypeError`。
17. **plotly 遗留出口要能容忍新 kind**：`/api/figure.json` 遇到没有 builder 的图层原本直接 500（`kind=heatmap 没有浏览器后端`）。D33 后它只是遗留路径，改成跳过该图层、返回 200，避免旧调用方被新功能带崩。
18. **quiver 的 `width` 不是线宽**：它是"箭杆宽度 = N 个 axes 宽度"，直接复用通用 `style["width"]`（1.6）会让每个箭头变成覆盖全图的色块——2026-10-31 实际踩到，整幅图糊成渐变。箭杆用独立键 `shaft`（默认 0.0035）。
19. **quiver 不要依赖 mpl 的自动缩放**：`angles="xy"` 下 auto-scale 按 axes 宽度归一，网格一密箭头就长到糊住。显式给 `scale` 且 `scale_units="xy"`，用「中位箭头 ≈ 跨度 6%」反算（`quiver_scale()`），换分辨率也不变形。
20. **quiver 没有 `arrowsize`**（那是 streamplot 的参数），要用 `headwidth/headlength/headaxislength` 换算；传错会抛 `AttributeError: Quiver.set() got an unexpected keyword argument 'arrowsize'`。
21. **`quiver`/`barbs`/`streamplot` 都不吃 `vmin/vmax` 关键字**：要传 `norm=Normalize(vmin, vmax)`，否则报 `AttributeError: Quiver.set() got an unexpected keyword argument 'vmin'`。色条范围与箭头颜色要一起改，别只改色条。
22. **纯色 vs 按值上色要互斥**：`color="#f00"` 时不能再传 `cmap`，也不能加 colorbar——否则箭头是单色、色条画的是模长，两者对不上，读者会被误导。
23. **3D 轴要按槽位建**：`fig.subplots()` 一律给 2D 轴，3D 必须逐格 `add_subplot(..., projection="3d")`；同一子图混排 2D/3D 要在建轴前就拦住（mpl 会在 draw 时才炸，报错位置很难读）。
24. **`DataStore` 原来只收 ≤2D**：3D 网格（x/y/z/u/v/w）是 (nz,ny,nx)，必须放宽到三维，否则 `add_data` 直接抛「最多二维」。
25. **`bar3d` 不吃 `cmap`**：想按高度上色得自己 `cmap(norm(values))` 生成颜色数组，否则柱子单色、色条却是 0–1 归一化刻度，两者对不上（截图时发现）。bar3d 与 hist3d 已统一按值上色，显式 `color` 才是单色。
26. **3D 分支提前 `return` 会丢标题与轴标签**：`_apply_view` 里 3D 分支原本直接返回，而 `set_xlabel/set_ylabel/set_title` 写在 2D 分支之后——评审发现 3D 子图的标题与轴标签全部静默丢失。3D 分支必须自己补 `xlabel/ylabel/zlabel/title`。
27. **`surface` 的 x/y 必须与 z 同形**：给了 x/y 却不校验形状，会静默画错位；现在形状不符直接报错。
28. **3D + colorbar 在小图里会触发 `constrained_layout not applied ... collapsed to zero`**：只是告警，mpl 会退回默认布局，出图正常；图再小就要手动调 `fraction/pad`。
29. **换 bundle 前先量两件事**：体积（实测 basic 1,102,006 B / cartesian 1,405,670 B / gl3d 1,678,645 B）与冷启动首帧（当前 862 ms，D21 门槛 1 s），再决定是否懒加载；不要先改代码再测。

## 6. 证据

- `docs/paper_panel_b.png`：matplotlib 正式图（论文 panel b 复刻）
- `docs/browser_paper.png`：同一份 spec 的浏览器交互态
- `docs/netlab_docked.png`：netlab 内停靠态（实时 5 s 窗口）
- `docs/netlab_replay.png`：netlab 内回放态（时间窗 2 s、游标 0.23 s）
- `docs/panel.png`：右栏面板（图层折叠卡片 / 分组 / 可拖宽）
- `docs/p13_render.png`：mpl 渲染管线在浏览器里的样子（双子图 + 右栏，2026-10-31）
- `docs/p13_kinds.png`：P13-01 四种图层同页（hist / pie / image+colorbar / table）
- `docs/p13_field.png`：P13-02 场类四联（heatmap / contour+clabel / contourf / correlation 带列名刻度）
- `docs/p13_vector.png`：P13-03 矢量场（quiver 按模长上色 + streamplot，各带 colorbar）
- `docs/p13_3d.png`：P13-04 3D 四联（surface / line3d / scatter3d / hist3d）
