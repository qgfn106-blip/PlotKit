# PlotKit 需求 · 决策 · 进度 · 经验（单一入口）

> 最后修改：2026-11-11（当前基线 562 passed；本轮补齐 PKF1 JSON 列边界与 DataSet 只读视图）
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
| **PK-R11** | 「在 plotkit 中实现 multiplotter 的所有绘图功能」 | 18 种 kind（11×2D + 7×3D）+ `correlation` 聚合全部可用，同一份 spec 出图 | **完成**：`registry.kinds()` **18 种核心全部完成**（11×2D + 7×3D，见 §3.3），另有扩展 kind（`contourf` / `correlation` / `barbs` / 信号族 / 三角族 / voxels 等），registry 共 **54** 种（P13-09 时 50，其后新增 `lic`、`volume`、`particles`、`segments` 四种共 54；`tools/coverage.py --check` 全绿） |
| **PK-R12** | 「以及 matplotlib API 中所有的绘图功能」 | 以 `Axes` 绘图方法为全集（约 55 个），逐个给出归属：独立 kind / 复用 kind / shapes / 轴级 / 不做 | **完成**：83 个 Axes/Axes3D 绘图方法全部归属，`tools/mpl_method_audit.py --check` 机器校验通过；归属表见 §3.4 |
| **PK-R13** | 「按照 multiplotter 中的逻辑进行预设计与编写程序」 | 预设表、分发别名、透传白名单、严格模式、`init()` 全局样式、`style_scope`、`register_layer` 契约 | **完成**：presets / 分发别名 / 透传白名单 / 严格模式 / `pk.init()` / `pk.style_scope()` / `pk.register_layer()` 全部落地（`src/plotkit/__init__.py`、`tests/test_pk_init.py`） |
| **PK-R14** | 「并且可自己优化」 | 允许偏离原实现：服务端分箱/相关矩阵、重绘缓存与 ETag、按像素宽度抽稀、节流刷新 | 部分已有（D22 缓存、min-max 抽稀） |
| **PK-R15** | 「开始前做好项目规划，确定需求，以及项目推进流程，验收标准」 | 需求 + 分期 + 四件套验收见 §3.5/§3.6 | 完成（2026-10-30） |
| **PK-R16** | 「以及持续更新文档」 | 每票收尾四处同步，不允许只改代码 | 执行中（§3.8 口径） |
| **PK-R17** | 「plotkit即使有了netlab预计算数据后依然无法播放」 | 有数据就要能播：时间范围不能依赖"用户先加图层" | **完成**（2026-11-03，§9）：`time_bounds()` 回退 `role="coord"` 数据集 |
| **PK-R18** | 「移动拖拽表格画布感觉不太合理，拖拽后难回到合理尺寸，并且持续窗口播放被打断」 | 拖拽不打断播放 + 一键复位尺寸 | **完成**（2026-11-03，§9）：拖动不重绘、松手重绘一次、「复位面板宽度」按钮 |
| **PK-R19** | 「图层设置希望是独立窗口，类似于netlab里的独立窗口」 | 图层面板可脱离右侧栏 | **已完成**（2026-11-03，方案 A 页内浮动窗口，可拖可缩、记住浮出状态；spec P3） |
| **PK-R20** | 「没法方便做到自行拖拽子图到合适区域，即子图能够相互重叠」 | 子图从网格改为自由矩形、可重叠、可拖拽缩放 | **已完成**（2026-11-03，`figure.layout` 自由矩形可重叠；spec P4） |
| **PK-R21** | 「不能自行放置文字框，数据标注，箭头等类似于笔记功能」 | 笔记级批注：文字框/箭头/框选/数据标注，存进 `figure.notes` | 已完成（2026-11-03，3.16.10；spec P5） |
| **PK-R22** | 前端 TypeScript 迁移：PlotKit 四个静态前端文件（`app.js` / `nsview.js` / `render2d.js` / `view3d.js`）纳入 netlab 主导的全局 JS→TS 迁移 | 与 netlab R41 同一口径：一期只加类型、1:1 编译、行为零变化；二期（P17）改原生 ES Modules（`app.js` 为模块入口，抽 `plot2d.utils`/`plot3d.utils`），由 esbuild 构建（`npm run build`） | **已完成（P16 一期 + P17 二期，2026-11-06）**：四文件全部严格类型化、tsc strict 0、AST 行为等价（verify_*_parity.js）；P17 原生 ESM 化、`plot2d.utils`/`plot3d.utils` 单测 19 passed；pytest 470 全绿；详见 netlab `REQUIREMENTS_AND_RULES.md` R41 / `PROGRESS.md` §7.76 |
| **PK-R23** | 全部 Python 代码按 PEP 8 规范化（TS 重构完成后） | 在 netlab R41 P16/P17 全部完成后，对 PlotKit 全部 Python 代码做 PEP 8 规范化与无损优化；不影响任何功能、不改公共接口与数值结果 | **已完成**（2026-11-06，`black` 规范化 92 文件、AST 等价校验通过（3 处仅 docstring 缩进差）、`pytest` 470 passed（当时历史数；当前基线 562）、`node test:utils` 19 passed；commit `32587c4`；详见 netlab R42 / P18） |
| **PK-R24** | 用户原话（2026-11-09）：「@docs\PLOTKIT_ORIGIN_REFACTOR_PLAN_2026-11-09.md 请就这个文档对plotkit项目进行复核，然后按照文档提出的规划进行代码优化 请遵守代码规范与文档规范 /to-spec /to-tickets 然后自行按照任务，开始完成任务，之间不要反复找我批准，只留下需要审批复核决策的操作」 | 复核 `docs/PLOTKIT_ORIGIN_REFACTOR_PLAN_2026-11-09.md` 的基线与证据，按 §8 P0「冻结契约」实施：L0 四份契约 JSON + 能力矩阵 8 行、L1 `FigureDocument` v1 与 0.1→v1 双向 golden、L2 `Frame` v1 wire、L3 `Selector` 唯一决策点与 `Decision`、X3 UI 状态不再落 cwd、三层测试与 CI 门禁；全部为纯新增或等价改进，P1–P5 的搬运/删接口/改宿主列为需审批决策项 | **P0 已实施（2026-11-09）**：复核报告 `docs/PLOTKIT_ORIGIN_REFACTOR_REVIEW_2026-11-09.md`；/to-spec 规格 `docs/specs/2026-11-09-p0-contract-freeze.md`；/to-tickets 票单 `.scratch/plotkit-origin-refactor/issues/01..12`；签字表 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0；基线 `pytest 470 passed`（HEAD c563707，当时历史数；当前基线 562）；本轮回归数字见签字表 G0 |
| **PK-R25** | 用户原话（2026-11-09，m01327）：「现在开始每次github上传更新都在readme中显示最近一次更新更新了什么，并且保留最近十次的更新记录可查阅」 | 每次 GitHub 上传前用 `tools/record_update.py --add` 把「日期/版本ref/更新内容/证据」写入 README 唯一 `<!-- UPDATE:LATEST:BEGIN/END -->` 标记块，并在 `docs/UPDATE_LOG.md` 滚动保留最近 10 条；`--check` 供 CI 校验两处逐字一致 | **已实施（2026-11-09）**：`record_update.py --check` → `entries=10 ok=True`，`tests/contract/test_record_update.py` 4 条全绿；工单 11 与 README 更新记录机制同批入 `docs/tickets/`。规则已写入全局长期记忆 |

## 2. 决策台账（D1–D41，摘录结论）

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
| D21 | 门槛修正：热重绘 <50 ms、冷启动 <1 s（**2026-10-31 修订**：mpl 单后端下 1200×700×6×20k 原实测 214 ms；同日经几何缓冲 + M4 + 视窗零拷贝 + 持久 Figure/blit + 统一 PNG 编码器优化后，热重绘 **48 ms**、冷导出 **111 ms**，**两项均已达标**，基线见 [BENCHMARKS.md](BENCHMARKS.md)） | `Plotly.react` 冷启动 ~180 ms，"首帧 <100 ms" 不可达 |
| D22 | GZip + 服务端构图缓存（`X-PlotKit-Cache`） | 同一 spec 反复取图不该重算 |
| D23 | 时间窗进 spec（`figure.window`），回放游标属 L3 不回写 | 静态导出与交互共用同一份数据口径 |
| D24 | `kind` 唯一图层类型；`layer.data` 按 kind 声明多键（`z/u/v/labels/values/image/cells`），`REQUIRED_DATA` 表驱动校验 | 不为每种图造新字段 |
| D25 | `LayerSpec` 增 `browser_native` / `fallback`；无浏览器等价的图**整图**走 mpl 出 PNG，不缝合 | 兜底策略变成字段与测试 |
| D26 | ~~前端按 `figure.caps` 懒加载 plotly 分部包~~ **作废（2026-10-31，D33 后不再有 plotly bundle）** | 历史记录：basic 1,102,006 B / cartesian 1,405,670 B / gl3d 1,678,645 B |
| D27 | 每 kind 一份 presets（默认 + 命名预设）；合并优先级 `KIND_DEFAULTS < init 全局 < add 参数 < **kwargs` | 对齐 MultiPlotter 的 KIND_DEFAULTS |
| D28 | 浏览器专属键走 passthrough 白名单，未列出记 warning；`strict=True` 抛错 | 防假兼容与静默丢参 |
| D29 | 动画 = spec 的 `figure.anim`（**只存时间切片，不存帧数据**）；每帧用 `render(t_end=…)` 现算，视窗锁在完整数据的范围上，PIL 合成 GIF（**2026-10-31 修订**：原写 `figure.frames` + `FuncAnimation` + MP4；实际用 `anim` 字段与逐帧渲染，MP4 需 ffmpeg 转 P13-07） | 动画与静态图同一条渲染路径，不会"两张图不一致"；spec 也不随帧数膨胀 |
| D30 | ~~统计/信号类先只做 mpl 兜底~~ **作废（2026-10-31，D33 后全部走 mpl）** | 历史记录 |
| D31 | 一切"要算的"在服务端（hist 分箱、correlation 矩阵、hexbin 计数、抽稀），前端只画 | 沿用 D10，避免两套数值 |
| D32 | 新增 kind 封口固定四件套（spec 往返 / plotly 快照 / mpl PNG / CDP 截图），并加"两后端都能出图"参数化用例 | 88 项全绿但渲染炸过 4 次 |
| D33 | **渲染统一 matplotlib（2026-10-31，用户定，修订 D1/D17）**：plotly 退役，浏览器只做呈现与编辑 | 用户原话「只能用 matplotlib 的绘图，用网页前端集中呈现，matplotlib 作为后端」。单一渲染路径 ⇒ 交互图与论文图同一套语义，不再维护两份 builder，也不会出现"浏览器画对了 mpl 画错"的漂移 |
| D34 | 交互 = **即时变换 + 提交重绘**：拖动/滚轮期间前端对高 DPI PNG 做 transform（0 延迟），停手 120 ms 才按新 xlim/ylim 回后端重绘；hover 读数由前端算，不触发重绘 | 保持"手感即时"，又不让每帧都走服务端 |
| D35 | 实时流 = 服务端**节流重绘**（默认 8 fps，可调 2–20）+ `ETag`/spec revision 缓存；数据按像素宽度抽稀（≤2 点/列） | PNG 重绘 ~60–100 ms/帧，60 fps 不可能；先保正确与可读 |
| D36 | inset 拖拽 = 前端覆盖层画框，松手 PUT spec 再重绘；`LayerSpec` 用 `interactive: bool` 取代 `browser_native` | 拖拽中不回后端，避免抖动 |
| D37 | **不删旧 canvas**：netlab 原生时间序列/示波器/李萨如/相图与分析面板长期保留，PlotKit 作为**并行**能力（2026-10-31 用户决定） | 用户明确要求「先不要将原生绘图分析删掉」；两条路径并存，谁都不阻塞谁 |
| D38 | **多后端框架**：`LayerSpec.builders` 支持按后端注册 builder；`dispatch` 负责选后端与回退；matplotlib 仍是默认与兜底，PyVista 作**可选三维工程后端**，VisPy 只留名字（2026-10-31 实现） | 三维在 mpl 上 10 万点要 1.4–6s（`Axes3D` 逐面片走 Agg），PyVista 交给 GPU 后 0.16–0.22s；但 VTK 常驻 ~165MB 且只出 PNG，所以不做全局替换 |
| D39 | **P0 只做等价改进与纯新增，不删任何能力（2026-11-09，PK-R24）**：四份契约 JSON 与能力矩阵落 `schema/`；`FigureDocument` v1 / 双向迁移落 `document/`；`Frame` v1 wire 落 `store/frame.py`；`Selector`/`Decision` 落 `backends/selector.py`（唯一决策点，不读环境变量 X6）；`host_api.probe()` 保持 `state` 三态与 `api_version="1"` 不变、只追加声明键；UI 状态默认落点由 `Path.cwd()/"layout.json"` 改为用户配置目录（X3），`create_app` 不隐式迁移；`/api/capabilities`、`/api/doc`、`/api/frame` 与 `X-PlotKit-Decision` 响应头均为纯新增 | `CODE_STANDARDS.md §0` 只许等价改进；计划 §10 X1–X10 要求保留全部绘图策略、禁止破坏性搬运；`api_version` 升 2 / 新三态、删 `PUT /api/spec`、收敛 `/api/column`、搬 contrib、改 `netlab/plotkit_bridge.py`、删文档资产均改变对外行为或跨仓，属需审批决策项，本轮不实施 |
| D40 | **裁定书 11 项收口（2026-11-09，PK-R24 续）**：⑨ probe 四字段拆分（`features` / 静态 `capabilities` / 动态 `optional` / 运行时 `decisions`）+ `capability.v1.json` 收紧；③ `get_layout()` 仅在 `using_default` 下 lazy 触发 `migrate_legacy_layout()`；⑪ 放行判据改 `collected == reports/test_baseline.json 的 pinned 常量 且 failed == 0 且四门禁零 violations 且 reports 二次生成 sha 不变`；⑩ 12 票入 `docs/tickets/` + README 更新记录机制；⑧ `BENCHMARKS.md` 删数字表、`bench_baseline.json` 唯一机器基线 + `bench_regress.py --check`；②PATCH 设计 / ④P1-0 测量 / ⑤test:ui 范围 / ⑥资产编目均只做设计或编目，不改对外行为 | `docs/PLOTKIT_P0_DECISIONS_2026-11-09.md` §二 逐项裁定、§四 执行顺序；G0 不自签（CI 首次绿灯与评审签字待用户），G1–G4 留白；`check_test_baseline.py` 把 `collected` 钉为 pinned 常量（数值见 `reports/test_baseline.json`，合法增量见 `docs/waivers.md` W-002），`check_layers.py` 加「契约加载器不得 import selector」 |
| D41 | **治理口径收口（2026-11-10，用户复核后续）**：① 判据性 544 硬编码全部改为「引用 `reports/test_baseline.json` 的 pinned 常量」，新增 W-002 如实记录 544→546→556 三次合法增量与前瞻规则（状态待用户追认，非事前豁免）；② 建 `docs/GOVERNANCE_SSOT_2026-11-10.md` 为仓内现行唯一口径 + 5 份治理文档同名归档指针（非原件），46 处悬空引用可解析；⑥ README / UPDATE_LOG 补 546 档、ref 改稳定批次标签 | `docs/GOVERNANCE_SSOT_2026-11-10.md` §3/§4/§5 与 `docs/waivers.md` W-002；X11 禁止事后补豁免故 W-002 标「待用户追认」；不 push、不 amend、不删 docs 资产；G3 / C-4 / G4 仍未达成 |

## 3. 图表能力扩展计划（P13 / D24–D36，2026-10-30 立项，2026-10-31 架构修订）

> 目标：从 3 种图层补齐到 MultiPlotter 的 18 种，并覆盖 matplotlib `Axes` 的约 55 个绘图方法。
> **架构（2026-10-31 用户定，D33）**：**渲染只用 matplotlib，网页前端只做集中呈现与编辑**；plotly 退役（新功能一律走 mpl）；netlab 的旧 canvas 与分析面板**不删**（D37）。
> 状态：P13 已完成（2026-10-31 立项的历史计划段落；当前 `plotkit.kinds()` 为 54 种，详见 §4 与 README）。

### 3.1 现状（实测，非转述）

- 2026-10-31 立项时快照：`registry.kinds()` = `('bar','line','marker')` → **3/18**；`spec/validate.py` 的 `REQUIRED_DATA` 也只有这三个 kind。当前 `plotkit.kinds()` 为 **54 kinds**（以代码为准）。
- （P13 前基线，plotly 已随 D33/P14-01 退役）前端当时走 plotly：`app.js:377` 用 `Plotly.react()`，数据取 `/api/figure.json`；vendored `plotly-basic.min.js` 1,102,006 B（分部包 cartesian 1,405,670 B / gl3d 1,678,645 B 原计划按 caps 懒加载）。
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

### 3.4 matplotlib 方法归属（83 个，`tools/mpl_method_audit.py` 机器可校验）

渲染全部走 mpl，分类依据变成「要不要 figure 级字段」而不是「浏览器有没有」：

| 组 | 方法 | 形态 |
| --- | --- | --- |
| 线/点/柱/面积 | plot, scatter, bar, barh, errorbar, fill_between, stackplot, stem, step, stairs, broken_barh, eventplot, vlines, hlines, axline | 独立 kind 或 `figure.shapes`（P13-05/07 完成 barh/stackplot/step/stem/stairs/broken_barh/eventplot；errorbar 走 line 的 error_x/y；vlines/hlines/axline 走 shapes） |
| 统计 | hist, hist2d, boxplot, violinplot, bxp, pie, ecdf, hexbin | 独立 kind（P13-05/07 完成 boxplot/violinplot/ecdf/hexbin/bxp；hist2d 用 heatmap 表达） |
| 图像/场 | imshow, matshow, pcolor, pcolormesh, contour, contourf, clabel, spy, figimage | 独立 kind（clabel 作为 contour 的 `labels=True`） |
| 矢量 | quiver, quiverkey, streamplot, barbs | 独立 kind（quiverkey 作为 quiver 的 `key=True`） |
| 三角/非结构 | triplot, tricontour, tricontourf, tripcolor | 独立 kind（P13-09 完成，Delaunay 自动三角化） |
| 信号 | psd, csd, specgram, cohere, acorr, xcorr, angle/magnitude/phase_spectrum | 全部完成（P13-07 psd/specgram；P13-09 其余 7 个） |
| 3D | plot, scatter, bar3d, hist3d, plot_surface, plot_wireframe, contour3D, contourf3D, quiver3D, voxels, trisurf, stem3D, text3D | 独立 kind 或 kind 参数（P13-09 补 voxels/trisurf/stem3D/text3D；wireframe/contour3D 走 surface 参数） |
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

**通用门槛**：PlotKit 测试只增不减（当前基线 562 passed，见 README/测试输出）；改前端跑 `npm run build`（esbuild：TS→ESM）、`npm run typecheck`，utils 单测 `npm run test:utils`；**重绘 < 120 ms（1200×700，6 通道 × 20k 点）**；实时刷新默认 8 fps 且可调；netlab 347 不回归。

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


### 3.9 覆盖率表（`tools/coverage.py` 历史生成，250 passed 时快照；当前基线 562 passed）

| kind | 维 | mpl 绘制器 | 数据键 | 预设 | 说明 |
| --- | --- | --- | --- | --- | --- |
| acorr | 2 | ✅ | x | ✅ | 自相关 |
| angle_spectrum | 2 | ✅ | x | ✅ | 相位谱 |
| bar | 2 | ✅ | x, y | ✅ | 柱状图 |
| bar3d | 3 | ✅ | x, y, z | ✅ | 三维柱状 |
| barbs | 2 | ✅ | x, y, u, v | ✅ | 风羽图（barbs） |
| barh | 2 | ✅ | x, y | ✅ | 横向柱状 |
| boxplot | 2 | ✅ | y | ✅ | 箱线图（多列 = 多箱） |
| broken_barh | 2 | ✅ | y | ✅ | 分段条形（甘特式） |
| bxp | 2 | ✅ | y | ✅ | 箱线图（由数据算统计量） |
| cohere | 2 | ✅ | x, y | ✅ | 相干函数 |
| contour | 2 | ✅ | z | ✅ | 等值线（可 clabel） |
| contourf | 2 | ✅ | z | ✅ | 填充等值线 |
| correlation | 2 | ✅ | z | ✅ | 相关系数矩阵（init-only 聚合） |
| csd | 2 | ✅ | x, y | ✅ | 互功率谱密度 |
| ecdf | 2 | ✅ | x | ✅ | 经验分布函数 |
| eventplot | 2 | ✅ | x | ✅ | 事件栅格图 |
| heatmap | 2 | ✅ | z | ✅ | 热图（z 或 x/y/z） |
| hexbin | 2 | ✅ | x, y | ✅ | 六边形分箱密度图 |
| hist | 2 | ✅ | x | ✅ | 直方图（服务端分箱） |
| hist3d | 3 | ✅ | x, y | ✅ | 三维直方（二维分箱 + 柱） |
| image | 2 | ✅ | image | ✅ | 图像 / 热图 |
| line | 2 | ✅ | x, y | ✅ | 折线 / 曲线（时间序列主力） |
| line3d | 3 | ✅ | x, y, z | ✅ | 三维折线 |
| magnitude_spectrum | 2 | ✅ | x | ✅ | 幅度谱 |
| marker | 2 | ✅ | — | ✅ | 散点 |
| phase_spectrum | 2 | ✅ | x | ✅ | 相位谱（unwrap） |
| pie | 2 | ✅ | labels, values | ✅ | 饼图 |
| psd | 2 | ✅ | x | ✅ | 功率谱密度 |
| quiver | 2 | ✅ | x, y, u, v | ✅ | 矢量箭头图 |
| quiver3d | 3 | ✅ | x, y, z, u, v, w | ✅ | 三维矢量箭头 |
| scatter3d | 3 | ✅ | x, y, z | ✅ | 三维散点 |
| specgram | 2 | ✅ | x | ✅ | 时频谱图 |
| stackplot | 2 | ✅ | x, y | ✅ | 堆叠面积（多行 = 多条序列） |
| stairs | 2 | ✅ | y | ✅ | 阶梯面积/阶梯线 |
| stem | 2 | ✅ | x, y | ✅ | 火柴杆图 |
| stem3d | 3 | ✅ | x, y, z | ✅ | 三维火柴杆 |
| step | 2 | ✅ | x, y | ✅ | 阶梯线 |
| stream3d | 3 | ✅ | x, y, z, u, v, w | ✅ | 三维流线（RK2 积分） |
| streamplot | 2 | ✅ | x, y, u, v | ✅ | 流线图（需二维网格） |
| surface | 3 | ✅ | z | ✅ | 三维曲面 |
| table | 2 | ✅ | cells | ✅ | 表格 |
| text3d | 3 | ✅ | x, y, z, labels | ✅ | 三维文字标注 |
| tricontour | 2 | ✅ | x, y, z | ✅ | 非结构等值线 |
| tricontourf | 2 | ✅ | x, y, z | ✅ | 非结构填充等值线 |
| tripcolor | 2 | ✅ | x, y, z | ✅ | 非结构伪彩 |
| triplot | 2 | ✅ | x, y | ✅ | 三角剖分线 |
| trisurf | 3 | ✅ | x, y, z | ✅ | 三角曲面 |
| violinplot | 2 | ✅ | y | ✅ | 小提琴图 |
| voxels | 3 | ✅ | z | ✅ | 体素图 |
| xcorr | 2 | ✅ | x, y | ✅ | 互相关 |

- registry 共 **50** 种；18 种矩阵覆盖 **18/18**
- 缺绘制器：无
- 18 种矩阵缺口：无

> 重跑：`PYTHONPATH=src python tools/coverage.py`；CI 用 `--check`（有缺项返回非零）。
>
> **口径**：18/18 指 §3.3 的 kind 覆盖。§3.4 的 mpl 方法表在 P13-09 又补了 15 个（triplot / tricontour(f) / tripcolor / voxels / trisurf / stem3D / text3D / csd / cohere / acorr / xcorr / angle·magnitude·phase_spectrum）。**PK-R12 已完成**：83 个 Axes/Axes3D 绘图方法在 `tools/mpl_method_audit.py` 全部归属（`--check` 通过），每个方法标为 kind / reuse / shapes / annotations / axis / skip 并给目标或原因。其中 `fill_between`→`stackplot`（或 shapes）、`hist2d`/`matshow`/`pcolor*`→`heatmap`、`clabel`→`contour(labels=True)`、`quiverkey`→`quiver(key=True)`、`errorbar`→`line(error_x/y)`；`figimage`/`spy` 明确 skip（与 `image`/`heatmap` 语义重合，不单建 kind）；`vlines`/`hlines`/`axline`/`axhspan`→`figure.shapes`；`twinx`/`twiny`/`secondary_*`/`colorbar`/`legend`/`grid`→轴级字段。自定义 kind 的渲染回退到 `reg.resolve(kind).builder`。

### 3.10 plotly 退役清单（D33）

| # | 项 | 状态 |
| --- | --- | --- |
| 1 | 页面不再加载 plotly（`index.html` 无 vendor script） | ✅ P13-00 |
| 2 | 前端渲染改 `<img>` + `/api/render` | ✅ P13-00 |
| 3 | 自包含导出 `fig.html()` 改内联 mpl SVG（不再内联 bundle） | ✅ P13-07 |
| 4 | `/api/figure.json` 仅遗留，遇到无 builder 的 kind 跳过而不是 500 | ✅ P13-02 |
| 5 | 删除 `static/vendor/plotly-basic.min.js`（1.1 MB）+ 精简 `server/assets.py` | ✅ P13-09（静态目录从 1.1 MB 降到 76 KB） |
| 5b | 删除 `backends/plotly_backend.py`（603 行）与 `Figure.plotly()` | ✅ P14-01（2026-10-31 用户批准） |
| 6 | 删除 `Figure.plotly()` / `self_contained_html()` / `/api/figure.json` | ✅ P14-01：方法、端点、`X-PlotKit-Cache` 缓存全部删除 |
| 7 | 后端无关的公共件迁出（`PALETTE`/`THEMES`/`color_for`/`_TRANGE`/`_window_slice`/`_xy`/`_step`/`time_bounds`） | ✅ P14-01：新模块 `backends/series.py` |
| 8 | `line`/`marker`/`bar` 三个基础图层的注册搬到 `mpl_backend`（原来靠 import plotly 后端注册） | ✅ P14-01 |
| 9 | 全仓清死代码与失效依赖 | ✅ P14-01：`ruff --select F401,F811,F841,E9` 全绿；`pyproject` 的 `desktop` extra 由 PySide6 改 pywebview |

> P14-01 同时修掉两处退役带出来的真问题：①`/api/clear` 里还引用着已删的 plotly 构图缓存（NameError）；②**`figure.window` 的实时窗口语义原先在 plotly 后端里实现**，删掉后会静默失效——现在由 `Figure.render_result()` 接管（无 `t_end` 时取「数据末尾往回 window 秒」）。

## 4. 当前进度

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| **P0 契约冻结**（PK-R24 / D39） | 复核 `docs/PLOTKIT_ORIGIN_REFACTOR_PLAN_2026-11-09.md` → L0 四份契约 JSON + 能力矩阵 8 行 / L1 `FigureDocument` v1 与 0.1→v1 双向 golden / L2 `Frame` v1 wire / L3 `Selector`+`Decision` / X3 UI 状态路径 / 纯新增 `/api/capabilities`、`/api/doc`、`/api/frame` 与 `X-PlotKit-Decision` / 三层测试 + `tools/check_*.py` + `python-tests.yml` | **已实施（2026-11-09）**：全部为纯新增或等价改进；基线 `470 passed`（HEAD `c563707`）；本轮回归与门禁输出见 `docs/PLOTKIT_ORIGIN_REFACTOR_SIGNOFF_2026-11-09.md` G0。P1–P5（contrib 搬运、删 `PUT /api/spec`、收敛 `/api/column`、`api_version` 升 2 / probe 新三态、改 `netlab/plotkit_bridge.py`、docs 瘦身）**未实施，列为需审批决策项** |
| **P0 裁定书收口**（PK-R25 / D40） | ⑨ 四字段拆分 / ③ lazy 迁移 / ⑪ collected 常量门禁 / ⑩ 12 票入仓 + README 更新记录 / ⑧ bench 相对回归带 / ②④⑤⑥ 设计与编目；`reports/test_baseline.json` 钉 `collected=544` | **已实施（2026-11-09 16:50）**：`pytest 544 passed`、`--collect-only 544 collected`、三层 `70 passed`、四门禁 `ok=True` 零 violations、`check_test_baseline ok=True`、`bench_regress check=ok`、`record_update entries=10 ok=True`、`reports/*.json` 二次生成 sha 不变；本地冻结提交与轻量 tag `p0-freeze-2026-11-09` 见工作区签字表 §0；不 push（代理未开），CI 首次绿灯待用户 |
| TS 迁移 | 四个静态前端文件纳入 netlab R41 全局 JS→TS（一期类型化 P16 + 二期模块化 P17：原生 ESM、抽 `plot2d.utils.ts`/`plot3d.utils.ts` 并补单测） | 已完成（2026-11-06；P16 tsc strict 0 / AST 行为等价；P17 ESM 化、utils 单测 19 passed；pytest 470 全绿） |
| Python PEP 8 | TS 重构完成后，PlotKit 全部 Python 代码按 PEP 8 规范化（无损、不改功能）；对应 netlab R42 / P18 | 已完成（2026-11-06；`black` 92 文件、pytest 470 passed、`node test:utils` 19 passed；见 PK-R23 / netlab R42 P18） |
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
| P13-05 | boxplot / violinplot / ecdf / hexbin / barh / stackplot / step / stem | ✅ 首批 8 种完成：`tests/test_kinds_stats.py` 14 项，全库 **208 passed**；浏览器四联截图见 §6。**未做**：stairs / broken_barh / eventplot / bxp / psd / specgram / csd / cohere / acorr / xcorr / 频谱族（转 P13-07） |
| P13-06 | 动画：`figure.anim` + 逐帧渲染 + GIF；前端「动画」按钮播放 | ✅ 完成：`tests/test_anim.py` 10 项，全库 **218 passed**；40 帧 / 700×440 首次 6.3 s、缓存后瞬时；CDP 实测按钮进入播放态。**未做**：MP4（需 ffmpeg，转 P13-07） |
| P13-07 | 漏项 6 种 + 表格高亮 + MP4 + 自包含导出改内联 SVG | ✅ 已做：stairs/broken_barh/eventplot/bxp/psd/specgram、`highlight=max/min/[[r,c]]`、MP4（ffmpeg）、`fig.html()` 内联 SVG。**未做**：`ScienceResult`/`SciencePlotter`、`shrink_field`、colorbar 细化（转 P13-09） |
| P13-09 | 方法级缺口 15 种 + plotly bundle 删除 | ✅ 完成：`tests/test_kinds_gaps.py` 16 项，全库 **250 passed**；registry **50 种**；`static/` 1.1 MB → 76 KB。**不做**：`ScienceResult`/`SciencePlotter`（用户 2026-10-31：改用模板保存 `save_spec`/`load_spec` 即可）；plotly 代码本体待批准删除 |
| P13-08 | 覆盖率表 / 性能回归 / plotly 退役清单 | **完成（性能部分 2026-10-31 达标）**：覆盖率 **18/18 + 50 种全部有绘制器**（`tools/coverage.py --check` 退出 0，234 passed）；性能基线见 [BENCHMARKS.md](BENCHMARKS.md)，回归脚本 `tools/bench_regress.py --check`：冷导出 PNG **111 ms**、热重绘 blit **48 ms**、抽稀 2M 点 **9 ms**、追加 2000 次 **35 ms**（均优于 D21 的 50/120 ms 目标，热重绘 <50 ms 已达成）；plotly 退役清单见 §3.10 |
| P14-01 | plotly 退役（D33 收尾） | ✅ 完成：删 `backends/plotly_backend.py`（603 行）、`Figure.plotly()`、`/api/figure.json`；新增 `backends/series.py` 承接公共件；**301 passed**（净减 15 条 plotly 专属用例，其余改写成 mpl 断言）；netlab **348 passed** |
| P15-00 | 三维交互视图（WebGL）：`/api/xyz` 二进制点云 + 前端 `view3d.js`，拖动只改矩阵 | ✅ 完成：WebView2 实测 2 图层 / 25k 点 **120 fps**；`tests/test_server.py` 4 条新用例，全库 **305 passed** |
| P15-01 | 二维实时预览：拖动/缩放中每 70ms 发一次半分辨率请求 | ✅ 完成：拖动中看到的是新视窗的真图（不再只是 CSS 拉伸），松手后 120ms 出全清图 |
| P15-02 | 服务端 hover 拾取：`/api/pick` 按视窗跨度归一化找最近数据点 | ✅ 完成：读数从"像素反推"变成真实数据点（含 `#索引`） |
| P15-03 | 三维矢量输出：`fmt=svg` 时 `dispatch` 一律回退 mpl（VTK 的 GL2PS 在本机只剩位图） | ✅ 完成：surface 600×420 SVG 161 KB / 731 ms / 890 个 `<path>`；pyvista 直接要 SVG 抛 `BackendUnsupported` |
| P15-04 | 前端 3D 视图画曲面：`/api/mesh` 二进制网格 + `view3d.js` 的 Lambert 着色 | ✅ 完成：WebView2 实测 120 fps、canvas 189 KB，带光照的 sombrero 曲面 |
| P15-05 | 数据金字塔：超 40 万点逐级 M4 摘要，按像素挑层 | ✅ 完成：300 万点抽稀 7.3→3.2 ms（2.3×）；端到端只占 <5%，属"为将来更大数据留的口子" |
| P15-06 | 三维并发：`pyvista_pool.render_many` 进程池批量出图 | ✅ 完成：40 帧 17.4 s → 8.9 s（4 worker，1.95×），逐字节一致；8 帧反而更慢（worker 启动 ~2 s） |
| P15-07 | 三维混合矢量出图（`hybrid3d`）：PyVista 位图 + mpl 矢量轴/刻度/色标/标题 | ✅ 完成：`PLOTKIT_3D_SVG=hybrid`（默认）/`mpl`（纯矢量回退）；800×600 SVG 249 KB，1 张位图 + 138 path + 24 text；新增 2 条测试，全库 **313 passed**；见 [THREE_D_BACKENDS.md](THREE_D_BACKENDS.md) §11 |
| P15-08 | 三维动画 API：`figure.anim3d()` 复用同一个离屏 Plotter，逐帧只改 actor 位姿/相机 | ✅ 完成：`anim3d.py` 提供 `add_box/add_points/add_trail/set_pose/orbit/frames_png/save_gif/save_mp4`；60 帧 560×380 **2.33 s（38.8 ms/帧）**，GIF 1.4 MB；新增 `tests/test_anim3d.py` 8 条，全库 **321 passed** |
| P15-09 | 三维视图自绘装饰：包围盒棱、三轴、刻度、轴名、标题、图例（2D canvas 叠在 WebGL 上） | ✅ 完成：`view3d.js` 的 `attachOverlay`/`_drawDecor`；相机默认距离 3.2r→4.4r（包围盒对角半径 √3·r 才装得下）；顺带修 `/api/mesh` 不接受 meshgrid 二维坐标的 bug（三维曲面之前静默退回点云） |
| P15-10 | 三维框选区域分析：Alt+拖 出框 → 服务端投影筛选 → 统计 min/max/mean/p05/p95 | ✅ 完成：`POST /api/region`（点乘 MVP 投到 NDC 再按矩形掩码，100 万点 5–10 ms）；面板 `#plot3d-region`；实测 3600 点选 2681 点（74.5%） |
| P15-11 | 三维时间轴：`(x,y,z,t)` 重采样成固定帧数，前端拖动/播放驱动 marker 与生长轨迹 | ✅ 完成：`GET /api/timeline?frames=240`；`setMarker`/`setTrail`（DYNAMIC_DRAW）；播放 50 ms/帧≈20fps；顺带修 `native.add()` 丢掉数据键 `t` 的 bug |
| P15-12 | 线积分卷积图层 `lic`：`lic_texture`/`lic_rgb`（blur 法，460² 约 1.2 s）、`step_px`/`contrast`/`seed` 可调 | ✅ 完成：`tests/test_lic_volume.py` 5 条；示例 `examples/vector_field_lic.py` 出 `docs/vector_field/01_lic_slice.png` |
| P15-13 | 体渲染图层 `volume`（仅 pyvista）：`add_volume` + 不透明度传递函数 + 逐图配色覆盖 | ✅ 完成：4 条测试；`02_volume_3d.png`（发光涡管 + 粒子环） |
| P14-00 | 多后端框架（D38）：`builders` 表 + `dispatch` + PyVista 三维后端 + `/api/render?backend=` | ✅ 完成：`tests/test_multibackend.py` 20 项，全库 **314 passed**；11 种三维 kind 全部可出图；`tools/bench_3d.py`（mpl vs pyvista）：surface 100² **714→173ms**、scatter3d 10 万 **1375→218ms**、voxels 25³ **5966→164ms**；详见 [THREE_D_BACKENDS.md](THREE_D_BACKENDS.md) §10 |

> 图表扩展的需求、矩阵、票单、验收与经验**全部在本文件**（§1 PK-R11–R16 / §2 D24–D32 / §3 计划 / §4 进度 / §5 经验）；netlab 侧只在 R32 留一行指针，不复制结论。

| P16-00 | 三维 NS 涡旋可视化（模式 A-prime）：自相似场 + WebGL2 体积/粒子 + 双轨诊断 + 实时调参 | ✅ 完成：`src/plotkit/ns/`（field/diagnostics/app）+ `static/ns.html`/`nsview.js` + `server/ns_app.py`；`tests/test_ns_field.py` 14 条 + `tests/test_ns_api.py` 6 条；1280×820 **98–120 fps**；不可压残差 2.1–2.5%；详见 [NS_VORTEX.md](NS_VORTEX.md) |
| P16-01 | 模式 B：真数值解（伪谱 NS 求解器 + `source=solver` 全链路） | ✅ 完成：`src/plotkit/ns/solver.py`（2/3 去混叠 + Heun RK2 + 每步投影 + 自适应 dt），32³/t=0.95 → 13.8 s / 48 帧 / 18.9 MB，峰值速度 0→0.444、峰值涡量 0→13.6、散度 ~1e-17；`/api/ns/*` 全部支持 `source=analytic|solver`，`/api/ns/state` 报进度，页面加数据源下拉；`create_app(with_ns=True)` 可把 NS 路由挂进主应用；`tests/test_ns_solver_api.py` 6 条，全库 **381 passed** |
| P16-02 | NS 规模与一致性验收（任务书 §12）：`tools/verify_ns.py` | ✅ 完成：10 万 48 fps / 50 万 10 fps / 100 万 5 fps（瓶颈是 JS 侧粒子推进）；四项一致性检查（跳转确定性、倍速不改物理、暂停续进、相机不改数据）全绿；粒子层加 8 帧历史流线（instanced LINE_STRIP，31→29 fps） |
| P16-05 | NS 场场景化：`pk.ns.scene.figure()` → 普通 spec（volume + particles）+ 主查看器入口 | ✅ 完成：`--figure` 模式 120 fps；Γ 2→8 时 u_max 比值 4.00；`tests/test_ns_scene.py` 5 条；规格与验收见 [NS_INTEGRATION.md](NS_INTEGRATION.md) |
| P16-06 | `segments` 图层 + coverage 控制台兼容 + NS 流线进主查看器 | ✅ 完成：`pk.kinds()` 54；`tests/test_ns_scene.py` 8 条；全量 **405 passed**；`docs/NS_INTEGRATION.md` 阶段 4 |
| P16-07 | Field3D 通用场景 + 三维批量渲染接口 + CLI `render3d` | ✅ 完成：`pk.field3d.scene()` 任意三维流场出图；`/api/render3d/batch` 出 zip；`plotkit render3d`；全量 **436 passed**；实测并发在本机反而更慢（48 帧 1.9 s vs 10.3 s，pickle 数据 + 每 worker import VTK），故默认进程内、`workers` 仅作逃生门（`docs/specs/2026-11-02-3d-field-and-batch-render.md`） |
| P16-08 | 编程时的即时出图 + 三维动画导出 + 等值面开关 + 散点场 | ✅ 完成：`pk.quick()` 一行出图（PNG/SVG，可写文件/打开）；`field3d.scene(iso=True/False/None)`；`ArrayField` 支持散点/非结构（桶网格最近点）；三维工具条「导出动画」→ `POST /api/render3d/batch` 出 zip；新增 9 条测试，全量 **436 passed**；规格 `docs/specs/2026-11-02-quick-plot-and-3d-export.md` |
| P16-09 | R5：多序列 quick / 逐帧 t / IDW 散点 / GPU 百万粒子 | ✅ 完成：`pk.quick(x, [y1,y2], labels=…)`；批量端点 `frames[].t`（进程内渲染）；散点场改 IDW（`scattered=True` 可显式声明）；**GPU 粒子修好**（uniform 设在 CPU 程序上的 bug）——12 万 63 fps / 50 万 64 fps / **100 万 47–50 fps**（任务书目标 30 fps）；新增 5 条测试，全量 **436 passed**；规格 `docs/specs/2026-11-02-r5-quick-time-idw-gpu.md` |
| P16-10 | R6：HDF5 读取 / 三维 LOD / netlab 仓库卫生 | ✅ 完成：`ArrayField` 支持 `.h5/.hdf5`（h5py 可选）；`field3d.auto_n(budget)` + `scene(n="auto")`；netlab `.gitignore` 放行 tests/docs（46+62 文件入库）；新增 3 条测试，全量 **436 passed** |
| P16-04 | 浏览器 3D 图层：`volume`（标量场 + 等值面）与 `particles`（时空点云） | ✅ 完成：`/api/volume`（field/surface 两种载荷）、`/api/particles`、view3d 的 mesh/点精灵渲染；`tests/test_web3d_layers.py` 5 条；`tools/verify_volume3d.py` 真机截图 `docs/web3d_volume.png` |
| P16-03 | GPU 粒子推进（实验，`?gpu=1`） | ⏸ **暂缓（2026-11-01 用户决定「先收手」）**：20 万粒子 GPU 58–79 fps 且可见（CPU 同条件 40–50）；50 万/100 万整层不可见，已排除链接/uniform/纹理单元/混合深度/历史 blit/uStride/冻结 advect，关键证据是位置纹理尾部全 0 → 疑在初始上传或取点映射。默认仍走 CPU 路径（12 万 41–49 fps）；证据见 [NS_VORTEX.md](NS_VORTEX.md) §19.1 |

**测试基线：PlotKit **470 passed**（2026-11-06，P16–P18 完成后；P16 各票入场时为 405/436 passed，早期 2026-11-02 为 421 passed）。

**性能实测（28 数据集 / 11 图层 / ~1.4k 点）**：冷启动首帧 862 ms、热重绘 13.7–83 ms、`figure.json` miss 6.8 ms / hit 4.8 ms（该端点已随 P14-01 删除，数字仅存史）。

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
9. **mpl 渲染的耗时结构**（2026-10-31 首测，1200×700 / 6 通道 / 20k 点）：`to_figure` ≈ 118 ms、`savefig` ≈ 190 ms，合计 ~310 ms；当时结论是"按像素抽稀压不动 savefig 这个常数"。
   **同日优化后更正**：`savefig` 的常数其实由**内部再 `draw()` 一次整图**（刻度/文本重算 ~28 ms）+ PNG 编码（~33 ms）构成。改用 `livecache.encode_png()` 直接从 canvas 缓冲编码、并复用持久 Figure 后：冷导出 **111 ms**、热重绘 blit **48 ms**、抽稀 2M 点 **9 ms**、追加 2000 次 **35 ms**（见 [BENCHMARKS.md](BENCHMARKS.md)）。教训：先分清"必要的栅格化"与"重复绘制"再谈常数。
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
29. **二维数据"按行还是按列"必须先定死**：boxplot/violinplot 原来按列切，传 (2,120) 的小提琴图画出 **120 个琴**糊成一片（截图才发现）。现在全库统一 **一行 = 一组 / 一条序列**（与 stackplot 同口径）。
30. **`boxplot(patch_artist=True)` 的箱体在 `ax.patches`，不在 `ax.artists`**：写断言时别数错集合。
31. **`ax.stem()` 不要用 `for line in ax.lines` 染色**：那会把同一子图里**其他图层**已经画好的 Line2D 一起改掉（评审发现）。要改就改 `StemContainer` 的 `markerline` / `stemlines`（茎线是 LineCollection，不在 `ax.lines` 里）。
32. **单序列 kind 收到二维数据要直接报错**：`step`/`stem`/`barh`/`ecdf`/`hexbin` 用 `_flat()` 取值，二维会抛「需要一维数据」并提示改用多图层——否则会把 (2,120) 拉成一条横跨两条序列的锯齿线。
33. **动画不要存"每帧数据快照"**：只存时间切片（`figure.anim`），每帧用 `render(t_end=…)` 现算——与交互渲染同一条路径，不会出现"动画和静态图不一致"，spec 也不会膨胀。
34. **GIF 合成用 PIL 就够**：`frames[0].save(..., save_all=True, append_images=frames[1:], duration=1000/fps, loop=0, disposal=2)`；MP4 要 ffmpeg，暂不做。
35. **动画接口是秒级的**：40 帧 / 700×440 首次 6.3 s（每帧 ~150 ms 的 mpl 渲染），必须走 ETag 缓存；前端点按钮后要等首帧，CDP 测试等待时间别设太短（我第一次等 6 s 只看到"没反应"）。
36. **动画必须锁视窗**：每帧都用 `t_end` 重新渲染时，mpl 会按"当前帧的数据"自动缩放，看起来是整幅图在放大而不是波形生长（评审发现）。`anim_limits()` 先用完整数据取一次范围，所有帧共用。
37. **`img.onload` 里 revoke 会漏**：并发/连点会覆盖回调，旧 blob URL 永不释放。改成设置新 src 后**立即** revoke 旧的；动画请求加 `state.animBusy` 守卫。
38. **`broken_barh` 的产物在 `ax.collections`**（BrokenBarHCollection），不在 `ax.patches`；`eventplot` 同理。
39. **`psd`/`specgram` 的 `noverlap` 必须 < `NFFT`**：默认值在小 NFFT 下会直接抛 `noverlap must be less than NFFT`，显式传 `nfft // 2` 最稳。
40. **自包含 HTML 改内联 SVG 后体积不小**：6×1200 点的图约 1 MB（SVG 是逐点路径），比内联 plotly bundle + 数据略小；点特别多时建议导出 PNG。
41. **`Axes.angle/magnitude/phase_spectrum` 没有 `NFFT` 参数**：它们只认 `pad_to`，传 `NFFT=` 会报 `Line2D.set() got an unexpected keyword argument 'NFFT'`（只有 psd/csd/cohere/specgram 才有 NFFT）。
42. **`cohere`/`csd` 的 `NFFT` 不能超过信号长度的一半**：分段平均至少要两段，否则抛 `Your signal is too short for your choice of *NFFT*`。
43. **换 bundle 前先量两件事**：体积（实测 basic 1,102,006 B / cartesian 1,405,670 B / gl3d 1,678,645 B）与冷启动首帧（当前 862 ms，D21 门槛 1 s），再决定是否懒加载；不要先改代码再测。

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
- `docs/p13_stats.png`：P13-05 统计族四联（boxplot / violinplot / hexbin+colorbar / stackplot）
- `docs/p13_gaps.png`：P13-09 方法级补齐四联（tricontourf / voxels / magnitude_spectrum / trisurf）

## 6. 三维与大规模后端评估（2026-10-31，只决策未实现）

- 结论：Matplotlib 保留为默认/回退；**PyVista 作可选 3D 工程后端**（网格/体场/矢量场）；**VisPy 预留**为百万级动态点线；**Trame 只做浏览器交互层**。
- 依据与本机基线：`surface 100²=619ms`、`scatter3d 10 万=1969ms`、`voxels 35³=4322ms`（800×600 冷渲染），三维在万级单元已比整张 2D 大图慢一个数量级。
- 三个硬边界：`LayerSpec` 单 builder 要改多后端 builders；三维数组不能 `dtype=float` 悄悄升精度；`stream3d` 必须保留 `algorithm="plotkit_rk2"` 兼容模式。
- 详见 [THREE_D_BACKENDS.md](THREE_D_BACKENDS.md)（逐 kind 映射、实施顺序、验收指标、不做清单）。

## 7. 实时面板性能（2026-11-02，D37，netlab 内嵌场景）

用户反馈「plotkit 卡顿」，在 netlab 内嵌（`/plotkit/?embed=1`，matplotlib 实时重绘）下定位到三条**代码级**问题并修复：

- **数据集长度错位**：运行中途出现的通道从 0 长度 `push`，与坐标列 `t` 永久错开，`render` 抛 `图层 x/y 长度不一致` → 曲线卡死。新数据集必须先 `np.full(len(t), nan)` 补齐；`_ingest` 每次 push 前统一对齐。
- **读写并发**：`store/registry.py` 新增模块级 `DATA_LOCK`（RLock）；`server/app.py::_cached` 用它把整个 `build()` 串行化（顺带避免多个 200ms 渲染排队积压）。**任何"后台线程在写、渲染线程在读"的用法都必须持有这把锁。**
- **渲染代价与频率**：6 曲线 528 点时 `figure.render` 900×520=72ms / 1200×700=149ms / 1600×950=191ms / 2400×1400=308ms，且持 GIL。故：`renderUrl` 面积上限 1400×1000 等比缩小；实时自动重绘节流 `LIVE_MIN_MS=1000`；轮询 500→1000ms；拖动预览 `PREVIEW_MS` 70→160ms、`PREVIEW_SCALE` 0.55→0.5；不可见（`document.hidden` / `offsetParent` / 宿主 `postMessage({type:'plotkit-visibility'})`）完全停；面板空图层时轮询顺手重取 `api/spec` 自愈。

效果（netlab 内嵌，`rlc_series`）：可见时 8 次渲染/8s（原约 2Hz），切走或关浮窗后 **0 次**；空场景先开面板也能自动长出 6 条曲线。

## 8. PlotView：数据与渲染解耦（2026-11-02）

**目标**：播放/缩放不再走服务端 matplotlib（单帧 20 s 级），数据只登记、图形由前端 canvas 自绘，matplotlib 仅用于定格导出。

**实现**
- `src/plotkit/static/render2d.js`（`window.Plot2D`）：canvas 2D 渲染器，支持 23 种 2D kind（line/step/stairs/stem/marker/scatter/points/bar/barh/segments/area/hist/ecdf/boxplot/violinplot/violin/pie/hexbin/quiver/table/heatmap/image/contour/contourf）+ `pick()` 悬停取值。
- `src/plotkit/server/app.py`：`GET /api/column?name=&pixels=` 单列 float32 + 保首尾抽稀（格式同 `PK01`）。
- 前端：`#plotCanvas` 与 `clientRenderable/ensureSeries/renderClient/replayRender`；滚轮光标锚定缩放、拖拽平移、双击复位；图层编辑器补全（图型/颜色/子图/数据/图例/线宽/线型/点形/点大小/不透明度/X-Y 范围/X-Y 刻度/网格/Y 翻转）+「画布与子图」（标题/列数/子图数/轴名）；design token 与 netlab 统一。

**实测**：前端 1.46 ms/帧（旧 72–308 ms/帧）；23 kind 全通过；双子图 axes=2；`tests/test_api_column.py` 3 passed、`tests/test_api.py` 17 passed。

**边界**：contourf 用色块近似（无等值线路径）；streamplot/3D 仍回落服务端。

## 9. 回放时间范围、拖拽复位与自由布局/批注（2026-11-03）

用户反馈（原话见 `docs/specs/2026-11-03-canvas-free-layout-annotations.md`）：预计算后仍无法播放、拖画布打断播放且难复位、图层设置要独立窗口、子图要能自由拖拽/重叠、要能放文字框/箭头/数据标注。

**已修复（PK-R17 / PK-R18）**
- 播放根因：`backends/series.py::time_bounds()` 只从图层 `x` 取范围；netlab 按 D-PlotView 只登记数据集、不建图层 → `/api/meta` 的 `time.min/max` 为 `null` → 前端 `playStep()` 恒返回 0，播放游标不动。修复：图层范围为空时回退 `role="coord"` 数据集（`_coord_time_bounds`）。实测预计算 1 s 后 `meta={'min':0.0005,'max':1.0,'count':600}`。
- 回归：`tests/test_window.py::test_time_bounds_falls_back_to_coord_data_without_layers`；netlab 侧 `test_plotkit_meta_has_time_range_after_precompute`。
- 拖拽：面板拖动只改 CSS、不逐帧重绘（重绘占 `state.busy`，`tickPlay` 会跳帧），松手重绘一次；「布局」组新增「复位面板宽度」按钮（等价双击 grip）。

**已实现（PK-R20 子图自由布局，2026-11-03）**
- 新增可选 `figure.layout = [{slot, rect:[x,y,w,h]}]`（figure 比例，y 从下往上，允许重叠）；`figure.subplots` 整数语义不变，没写 layout 时渲染与改前一致。
- 后端：`backends/mpl_backend.py::_grid_rect()` 抽网格矩形；`to_figure()` 解析 layout，命中槽位走 `fig.add_axes(rect)` 并 `set_layout_engine("none")`；`spec/validate.py` 校验 layout（slot 非负整数不重复、rect 4 数且 w/h>0、范围 -0.5…1.5）；`api/native.py` 的 `update_layout` 白名单加 `layout`。
- 前端：「布局」组新增「自由布局 / 回到网格」；开关时用服务端 `X-PlotKit-Axes` 包围盒 materialize；`#layout-overlay` 里虚线框可拖拽/拖角缩放，松手 `commit`；自由布局强制走服务端渲染（前端 canvas 不设 `state.img`，否则框没有几何）。
- 实测（无头 Edge）：开启→两槽 rect 各自落位；拖动 40/20px 后持久化；两槽拖到同一位置重叠成立；回到网格后 overlay 隐藏、恢复前端渲染。
- 回归：`PlotKit/tests/test_free_layout.py` 11 项全绿；用旧 vendored 代码跑同测试 8 failed（证明能红）。

**已实现（PK-R21 画布批注，2026-11-03，3.16.10）**
- 新增可选 `figure.notes`，条目 `{id, kind, text, color, size, …}`，`kind` ∈ `text`（`pos` 文字框）/ `arrow`（`start`→`end`）/ `region`（`rect` 虚线框）/ `mark`（`subplot` + 数据坐标 `x`/`y` 引线标注）。`text`/`arrow`/`region` 用 figure 比例坐标，`mark` 用数据坐标，缩放平移后仍跟着数据点。
- 后端：`spec/model.py` 加 `NOTE_TYPES` 与 `new_note()`；`spec/validate.py` 加 `notes` 白名单与逐条校验；`backends/mpl_backend.py::_draw_notes()` 用 `fig.text` / `FancyArrowPatch` / `Rectangle` / `ax.annotate` 绘制，在 `_draw_decorations()` 之后调用；`api/native.py` 的 `update_layout` 白名单加 `notes`。
- 前端：「布局」组新增「文字框 / 箭头 / 框选 / 数据标注 / 删除批注」；`#note-overlay` 按图像 rect 定位，点/拖建批注，拖动移动、双击改字、Delete 删除、Esc 退出工具；有批注时强制服务端渲染（前端 canvas 不写 `state.img`，覆盖层没有几何）。
- 实测（无头 Edge + CDP）：4 类批注依次创建并 `GET /api/spec` 读到 4 条；数据标注落在 `x=1.4349, y=2.5064`；双击改字同步；删除第一条后剩 `arrow/region/mark`；截图确认虚线框、箭头、引线、文字框都进了 PNG。
- 回归：`PlotKit/tests/test_notes.py` 14 项全绿；改前端前静态护栏断言为红（`note-overlay` 不存在）。

**不做**：完整矢量编辑器（Veusz/ParaView 那种）、批注富文本/旋转/多选批量拖动。

**已实现（PK-R19 图层独立窗口，2026-11-03，方案 A）**
- 「布局」组新增「图层独立窗口 / 图层已浮出」开关；浮窗 `#layerWin` 挂在 `.plotwrap` 上，标题栏可拖、右下角可缩、最小 260×180，`clampLayerWinRect()` 夹在画布内。
- 浮出/收起是把 `#layerSect`（图层 `<details>` 整块）在 `#panel` 与 `#layerWinBody` 之间搬 DOM，不重建内容，`renderLayers()` 照旧按 id 写入。
- `localStorage["pk.layerWin"] = {popped, rect}`：记住位置/尺寸与浮出状态，刷新还原；收起后刷新不会自己弹出来。
- 实测（无头 Edge + CDP，15 项断言全 PASS）：浮出搬运、拖标题栏 −120/+80、拖右下角 380×418→450×468、收起归位、刷新保持收起、再浮出后刷新还原 450×468。
- 回归：`PlotKit/tests/test_layer_window.py` 5 项全绿；用 P4 备份的旧静态文件对照，8 个关键标记全缺（能红）。
- 方案 B（独立浏览器窗口 + BroadcastChannel）留作 A 之上的「弹出」按钮，未做；C 依赖桌面壳，不做。
